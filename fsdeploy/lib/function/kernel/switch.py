"""
fsdeploy.function.kernel.switch
================================
Bascule le noyau actif via symlinks.

Le noyau actif est défini par des liens symboliques :
  /boot/vmlinuz → vmlinuz-<version>
  /boot/initramfs.img → initramfs-<version>.img
"""

from pathlib import Path
from typing import Any

from scheduler.model.task import Task
from scheduler.model.resource import Resource, KERNEL
from scheduler.model.lock import Lock
from scheduler.security.decorator import security


@security.kernel.switch
class KernelSwitchTask(Task):
    """Bascule le noyau actif via symlinks."""

    def required_resources(self):
        return [KERNEL]

    def required_locks(self):
        return [Lock("kernel", owner_id=str(self.id))]

    def run(self) -> dict[str, Any]:
        version = self.params.get("version", "")
        boot_path = Path(self.params.get("boot_path", "/boot"))

        if not version:
            raise ValueError("kernel version required")

        vmlinuz = boot_path / f"vmlinuz-{version}"
        if not vmlinuz.exists():
            raise FileNotFoundError(f"Kernel not found: {vmlinuz}")

        # Créer les symlinks
        links = {}

        vmlinuz_link = boot_path / "vmlinuz"
        self._safe_symlink(vmlinuz, vmlinuz_link)
        links["vmlinuz"] = str(vmlinuz_link)

        # Initramfs
        for pattern in (f"initramfs-{version}.img", f"initrd.img-{version}"):
            initramfs = boot_path / pattern
            if initramfs.exists():
                initramfs_link = boot_path / "initramfs.img"
                self._safe_symlink(initramfs, initramfs_link)
                links["initramfs"] = str(initramfs_link)
                break

        # System.map
        sysmap = boot_path / f"System.map-{version}"
        if sysmap.exists():
            sysmap_link = boot_path / "System.map"
            self._safe_symlink(sysmap, sysmap_link)
            links["System.map"] = str(sysmap_link)

        return {
            "version": version,
            "links": links,
            "active": True,
        }

    def _safe_symlink(self, target: Path, link: Path) -> None:
        """Crée un symlink en supprimant l'ancien s'il existe."""
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to(target.name)  # relatif


@security.kernel.install(require_root=True)
class KernelInstallTask(Task):
    """Installe un noyau depuis un package .deb ou un chemin."""

    def required_resources(self):
        return [KERNEL]

    def required_locks(self):
        return [Lock("kernel", owner_id=str(self.id), exclusive=True)]

    def run(self) -> dict[str, Any]:
        source = self.params.get("source", "")
        boot_path = Path(self.params.get("boot_path", "/boot"))

        if not source:
            raise ValueError("kernel source required (path or package)")

        if source.endswith(".deb"):
            return self._install_deb(source, boot_path)
        elif Path(source).is_file():
            return self._install_file(source, boot_path)
        else:
            raise ValueError(f"Unknown kernel source format: {source}")

    def _install_deb(self, deb_path: str, boot_path: Path) -> dict:
        result = self.run_cmd(f"dpkg -i {deb_path}", sudo=True, timeout=120)
        # Extraire la version installée
        r = self.run_cmd(f"dpkg-deb -f {deb_path} Package", check=False)
        version = r.stdout.strip().replace("linux-image-", "")
        return {"method": "deb", "version": version, "installed": result.success}

    def _install_file(self, source: str, boot_path: Path) -> dict:
        src = Path(source)
        dest = boot_path / src.name
        self.run_cmd(f"cp {src} {dest}", sudo=True)
        return {"method": "file", "path": str(dest), "installed": True}


@security.kernel.compile(require_root=True)
class KernelCompileTask(Task):
    """Compile un noyau depuis les sources."""

    executor = "threaded"  # opération longue

    def required_resources(self):
        return [KERNEL, Resource("system.cpu")]

    def required_locks(self):
        return [Lock("kernel", owner_id=str(self.id), exclusive=True)]

    def run(self) -> dict[str, Any]:
        source_dir = Path(self.params.get("source_dir", "/usr/src/linux"))
        config = self.params.get("config", "")
        jobs = self.params.get("jobs", os.cpu_count() or 4)

        if not source_dir.is_dir():
            raise FileNotFoundError(f"Kernel source not found: {source_dir}")

        # Config
        if config and Path(config).is_file():
            self.run_cmd(f"cp {config} {source_dir}/.config")
        elif not (source_dir / ".config").exists():
            self.run_cmd("make defconfig", cwd=source_dir)

        # Compile
        self.run_cmd(f"make -j{jobs}", cwd=source_dir, timeout=3600)
        self.run_cmd("make modules_install", cwd=source_dir, sudo=True, timeout=600)
        self.run_cmd("make install", cwd=source_dir, sudo=True, timeout=120)

        # Extraire la version
        r = self.run_cmd("make kernelversion", cwd=source_dir, check=False)
        version = r.stdout.strip()

        return {"version": version, "compiled": True}


import os
