"""
fsdeploy.function.kernel.switch
================================
Opérations sur les kernels : switch, install, compile.

Principe :
  - Switch : symlinks vmlinuz et initramfs.img
  - Install : depuis .deb ou fichiers directs
  - Compile : depuis sources avec config
"""

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from scheduler.model.task import Task
from scheduler.model.resource import Resource, KERNEL
from scheduler.model.lock import Lock
from scheduler.security.decorator import security


@security.kernel.switch
class KernelSwitchTask(Task):
    """
    Bascule le kernel actif via symlinks.
    
    Crée/met à jour :
      - /boot/vmlinuz → vmlinuz-<version>
      - /boot/initramfs.img → initramfs-<version>.img
    """

    def required_resources(self):
        return [KERNEL]

    def required_locks(self):
        return [Lock("kernel", owner_id=str(self.id), exclusive=True)]

    def run(self) -> dict[str, Any]:
        version = self.params.get("version", "")
        boot_path = Path(self.params.get("boot_path", "/boot"))

        if not version:
            raise ValueError("kernel version required")

        # Trouver le kernel
        kernel_file = None
        for pattern in (f"vmlinuz-{version}", f"bzImage-{version}"):
            p = boot_path / pattern
            if p.exists():
                kernel_file = p
                break

        if not kernel_file:
            raise FileNotFoundError(f"Kernel {version} not found in {boot_path}")

        # Trouver l'initramfs
        initramfs_file = None
        for pattern in (f"initramfs-{version}.img", f"initrd.img-{version}"):
            p = boot_path / pattern
            if p.exists():
                initramfs_file = p
                break

        results = {
            "version": version,
            "kernel": str(kernel_file),
            "initramfs": str(initramfs_file) if initramfs_file else None,
            "switched": False,
        }

        # Créer les symlinks
        vmlinuz_link = boot_path / "vmlinuz"
        if vmlinuz_link.is_symlink() or vmlinuz_link.exists():
            vmlinuz_link.unlink()
        vmlinuz_link.symlink_to(kernel_file.name)
        results["vmlinuz_link"] = str(vmlinuz_link)

        if initramfs_file:
            initramfs_link = boot_path / "initramfs.img"
            if initramfs_link.is_symlink() or initramfs_link.exists():
                initramfs_link.unlink()
            initramfs_link.symlink_to(initramfs_file.name)
            results["initramfs_link"] = str(initramfs_link)

        results["switched"] = True
        return results


@security.kernel.install(require_root=True)
class KernelInstallTask(Task):
    """
    Installe un kernel depuis un .deb ou des fichiers directs.
    
    Params:
      - source: chemin vers .deb ou répertoire
      - boot_path: destination
    """

    executor = "threaded"

    def required_resources(self):
        return [KERNEL]

    def required_locks(self):
        return [Lock("kernel", owner_id=str(self.id), exclusive=True)]

    def run(self) -> dict[str, Any]:
        source = Path(self.params.get("source", ""))
        boot_path = Path(self.params.get("boot_path", "/boot"))
        make_active = self.params.get("make_active", True)

        if not source.exists():
            raise FileNotFoundError(f"Source not found: {source}")

        results = {
            "source": str(source),
            "boot_path": str(boot_path),
            "installed": False,
            "version": "",
        }

        if source.suffix == ".deb":
            # Installation depuis .deb
            results.update(self._install_from_deb(source, boot_path))
        elif source.is_dir():
            # Installation depuis répertoire
            results.update(self._install_from_dir(source, boot_path))
        elif source.name.startswith("vmlinuz"):
            # Installation fichier direct
            results.update(self._install_direct(source, boot_path))
        else:
            raise ValueError(f"Unknown source format: {source}")

        # Activer si demandé
        if make_active and results.get("version"):
            switch_task = KernelSwitchTask(
                id=f"switch_{results['version']}",
                params={
                    "version": results["version"],
                    "boot_path": str(boot_path),
                },
            )
            switch_task.run()
            results["activated"] = True

        return results

    def _install_from_deb(self, deb_path: Path, boot_path: Path) -> dict:
        """Installe depuis un paquet .deb."""
        # Extraire le .deb
        extract_dir = Path("/tmp/kernel-install")
        extract_dir.mkdir(parents=True, exist_ok=True)

        self.run_cmd(f"dpkg-deb -x {deb_path} {extract_dir}", sudo=True)

        # Trouver vmlinuz et config
        vmlinuz = None
        config = None
        system_map = None
        version = ""

        for f in extract_dir.rglob("vmlinuz-*"):
            vmlinuz = f
            version = f.name.replace("vmlinuz-", "")
            break

        for f in extract_dir.rglob(f"config-{version}"):
            config = f
            break

        for f in extract_dir.rglob(f"System.map-{version}"):
            system_map = f
            break

        if not vmlinuz:
            raise FileNotFoundError("vmlinuz not found in .deb")

        # Copier vers boot
        shutil.copy2(vmlinuz, boot_path / vmlinuz.name)
        if config:
            shutil.copy2(config, boot_path / config.name)
        if system_map:
            shutil.copy2(system_map, boot_path / system_map.name)

        # Installer les modules si présents
        modules_src = extract_dir / "lib" / "modules" / version
        if modules_src.is_dir():
            modules_dst = Path("/lib/modules") / version
            if modules_dst.exists():
                shutil.rmtree(modules_dst)
            shutil.copytree(modules_src, modules_dst)

        # Cleanup
        shutil.rmtree(extract_dir, ignore_errors=True)

        return {
            "installed": True,
            "version": version,
            "method": "deb",
        }

    def _install_from_dir(self, source_dir: Path, boot_path: Path) -> dict:
        """Installe depuis un répertoire contenant vmlinuz, config, etc."""
        version = ""

        for f in source_dir.glob("vmlinuz-*"):
            version = f.name.replace("vmlinuz-", "")
            shutil.copy2(f, boot_path / f.name)

        for pattern in ("config-*", "System.map-*", "initramfs-*.img"):
            for f in source_dir.glob(pattern):
                shutil.copy2(f, boot_path / f.name)

        return {
            "installed": True,
            "version": version,
            "method": "directory",
        }

    def _install_direct(self, vmlinuz: Path, boot_path: Path) -> dict:
        """Installe un fichier vmlinuz direct."""
        # Extraire la version du nom
        match = re.search(r"vmlinuz-(.+)", vmlinuz.name)
        version = match.group(1) if match else "custom"

        shutil.copy2(vmlinuz, boot_path / vmlinuz.name)

        return {
            "installed": True,
            "version": version,
            "method": "direct",
        }


@security.kernel.compile(require_root=True)
class KernelCompileTask(Task):
    """
    Compile un kernel depuis les sources.
    
    Params:
      - source_dir: répertoire des sources (/usr/src/linux)
      - config: fichier .config ou "defconfig" / "oldconfig"
      - jobs: nombre de jobs parallèles
      - install: installer après compilation
    """

    executor = "threaded"

    def required_resources(self):
        return [KERNEL]

    def required_locks(self):
        return [Lock("kernel.compile", owner_id=str(self.id), exclusive=True)]

    def run(self) -> dict[str, Any]:
        source_dir = Path(self.params.get("source_dir", "/usr/src/linux"))
        config = self.params.get("config", "oldconfig")
        jobs = self.params.get("jobs", os.cpu_count() or 4)
        install = self.params.get("install", True)
        boot_path = Path(self.params.get("boot_path", "/boot"))

        if not source_dir.is_dir():
            raise FileNotFoundError(f"Source directory not found: {source_dir}")

        # Vérifier qu'on a un Makefile
        if not (source_dir / "Makefile").exists():
            raise FileNotFoundError(f"No Makefile in {source_dir}")

        results = {
            "source_dir": str(source_dir),
            "jobs": jobs,
            "compiled": False,
            "installed": False,
            "version": "",
        }

        # Configuration
        if config == "defconfig":
            self.run_cmd("make defconfig", cwd=source_dir, sudo=True)
        elif config == "oldconfig":
            self.run_cmd("make oldconfig", cwd=source_dir, sudo=True)
        elif config == "menuconfig":
            raise ValueError("menuconfig requires interactive terminal")
        elif Path(config).exists():
            shutil.copy2(config, source_dir / ".config")
            self.run_cmd("make olddefconfig", cwd=source_dir, sudo=True)

        # Extraire la version
        r = self.run_cmd("make kernelversion", cwd=source_dir, check=False)
        version = r.stdout.strip() if r.success else "unknown"
        results["version"] = version

        # Compilation
        self.run_cmd(
            f"make -j{jobs} bzImage modules",
            cwd=source_dir,
            sudo=True,
            timeout=3600,  # 1 heure max
        )
        results["compiled"] = True

        # Installation
        if install:
            # Installer les modules
            self.run_cmd(
                f"make modules_install",
                cwd=source_dir,
                sudo=True,
            )

            # Copier le kernel
            bzimage = source_dir / "arch" / "x86" / "boot" / "bzImage"
            if not bzimage.exists():
                bzimage = source_dir / "arch" / "x86_64" / "boot" / "bzImage"

            if bzimage.exists():
                dest = boot_path / f"vmlinuz-{version}"
                shutil.copy2(bzimage, dest)
                results["kernel_path"] = str(dest)

            # Copier la config
            config_src = source_dir / ".config"
            if config_src.exists():
                shutil.copy2(config_src, boot_path / f"config-{version}")

            # Copier System.map
            sysmap = source_dir / "System.map"
            if sysmap.exists():
                shutil.copy2(sysmap, boot_path / f"System.map-{version}")

            results["installed"] = True

        return results


# Re-exports pour les imports depuis kernel/
__all__ = ["KernelSwitchTask", "KernelInstallTask", "KernelCompileTask"]
