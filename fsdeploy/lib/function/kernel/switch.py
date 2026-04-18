# -*- coding: utf-8 -*-
"""
fsdeploy.function.kernel.switch
================================
Bascule le noyau actif via symlinks.

Le noyau actif est defini par des liens symboliques :
  <staging_dir>/vmlinuz -> vmlinuz-<version>
  <staging_dir>/initramfs.img -> initramfs-<version>.img

ZERO chemin en dur : tout est pilote par config/preset/params.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from scheduler.model.task import Task
from scheduler.model.resource import Resource, KERNEL
from scheduler.model.lock import Lock
from scheduler.security.decorator import security


# ===================================================================
# HELPERS
# ===================================================================

def _resolve_boot_path(params: dict) -> Path:
    """
    Resout le repertoire de boot depuis les params.
    Priorite : params["boot_path"] > params["staging_dir"] > params["boot_mount"].
    Leve ValueError si aucun n'est configure.
    """
    for key in ("boot_path", "staging_dir", "boot_mount"):
        val = params.get(key, "")
        if val:
            return Path(val)
    raise ValueError(
        "boot_path, staging_dir, or boot_mount required "
        "(from config kernel.staging_dir or pool.boot_mount)"
    )


# ===================================================================
# TASKS
# ===================================================================

@security.kernel.switch
class KernelSwitchTask(Task):
    """
    Bascule le noyau actif via symlinks.

    Params attendus (tous depuis config/preset, aucun en dur) :
      - version: str         Version du kernel (ex: 6.12.0)
      - boot_path: str       Repertoire contenant les kernels (ou staging_dir/boot_mount)
      - staging_dir: str     Fallback pour boot_path
      - boot_mount: str      Fallback pour staging_dir
      - kernel_prefixes: list[str]    Prefixes reconnus (defaut depuis config)
      - initramfs_prefixes: list[str] Prefixes initramfs reconnus
      - link_names: dict     Noms personnalises des symlinks
                             (defaut: {"kernel": "vmlinuz", "initramfs": "initramfs.img",
                              "sysmap": "System.map"})
    """

    def required_resources(self):
        return [KERNEL]

    def required_locks(self):
        return [Lock("kernel", owner_id=str(self.id))]

    def run(self) -> dict[str, Any]:
        version = self.params.get("version", "")
        if not version:
            raise ValueError("kernel version required")

        boot_path = _resolve_boot_path(self.params)
        kernel_prefixes = self.params.get("kernel_prefixes",
                                          ["vmlinuz-", "vmlinux-", "bzImage-"])
        initramfs_prefixes = self.params.get("initramfs_prefixes",
                                              ["initramfs-", "initrd.img-", "initrd-"])
        link_names = self.params.get("link_names", {})

        # Noms des symlinks (configurables)
        kernel_link_name = link_names.get("kernel", "vmlinuz")
        initramfs_link_name = link_names.get("initramfs", "initramfs.img")
        sysmap_link_name = link_names.get("sysmap", "System.map")

        # Trouver le fichier kernel
        vmlinuz = self._find_kernel(boot_path, version, kernel_prefixes)
        if not vmlinuz:
            raise FileNotFoundError(
                f"Kernel version {version} not found in {boot_path} "
                f"(prefixes: {kernel_prefixes})"
            )

        links = {}

        # Symlink kernel
        kernel_link = boot_path / kernel_link_name
        self._safe_symlink(vmlinuz, kernel_link)
        links["kernel"] = str(kernel_link)
        links["kernel_target"] = vmlinuz.name

        # Chercher et symlinker initramfs
        initramfs = self._find_initramfs(
            boot_path, version, initramfs_prefixes)
        if initramfs:
            initramfs_link = boot_path / initramfs_link_name
            self._safe_symlink(initramfs, initramfs_link)
            links["initramfs"] = str(initramfs_link)
            links["initramfs_target"] = initramfs.name

        # System.map
        sysmap = boot_path / f"System.map-{version}"
        if sysmap.exists():
            sysmap_link = boot_path / sysmap_link_name
            self._safe_symlink(sysmap, sysmap_link)
            links["sysmap"] = str(sysmap_link)
            links["sysmap_target"] = sysmap.name

        return {
            "version": version,
            "boot_path": str(boot_path),
            "links": links,
            "active": True,
        }

    def _find_kernel(
        self, boot_path: Path, version: str, prefixes: list[str],
    ) -> Path | None:
        """Trouve un fichier kernel par version et prefixes."""
        for pfx in prefixes:
            candidate = boot_path / f"{pfx}{version}"
            if candidate.exists():
                return candidate
        # Chercher aussi sans tiret (ex: vmlinuz6.12.0)
        for pfx in prefixes:
            pfx_no_dash = pfx.rstrip("-")
            candidate = boot_path / f"{pfx_no_dash}{version}"
            if candidate.exists():
                return candidate
        return None

    def _find_initramfs(
        self, boot_path: Path, version: str, prefixes: list[str],
    ) -> Path | None:
        """Trouve un initramfs correspondant a la version."""
        # Essayer les combinaisons comme zfsbootmenu-core.sh
        for pfx in prefixes:
            for ext in (".img", ""):
                candidate = boot_path / f"{pfx}{version}{ext}"
                if candidate.exists():
                    return candidate

        # Extensions supplementaires
        for ext in ("", ".img", ".gz", ".xz", ".zstd", ".lz4"):
            for pfx in prefixes:
                for name in (f"{pfx}{version}{ext}",
                             f"{pfx}{ext}{version}"):
                    candidate = boot_path / name
                    if candidate.exists():
                        return candidate
        return None

    def _safe_symlink(self, target: Path, link: Path) -> None:
        """Cree un symlink relatif en supprimant l'ancien s'il existe."""
        if link.is_symlink() or link.exists():
            link.unlink()
        # Symlink relatif (juste le nom de fichier si meme repertoire)
        if target.parent == link.parent:
            link.symlink_to(target.name)
        else:
            rel = os.path.relpath(str(target), str(link.parent))
            link.symlink_to(rel)


@security.kernel.install(require_root=True)
class KernelInstallTask(Task):
    """
    Installe un noyau depuis un package .deb ou un chemin.

    Params :
      - source: str      Chemin du .deb ou du fichier kernel
      - boot_path: str   Repertoire cible (ou staging_dir/boot_mount)
      - staging_dir: str Fallback
      - boot_mount: str  Fallback
    """

    def required_resources(self):
        return [KERNEL]

    def required_locks(self):
        return [Lock("kernel", owner_id=str(self.id), exclusive=True)]

    def run(self) -> dict[str, Any]:
        source = self.params.get("source", "")
        boot_path = _resolve_boot_path(self.params)

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
        r = self.run_cmd(f"dpkg-deb -f {deb_path} Package", check=False)
        version = r.stdout.strip().replace("linux-image-", "")
        return {"method": "deb", "version": version,
                "installed": result.success, "boot_path": str(boot_path)}

    def _install_file(self, source: str, boot_path: Path) -> dict:
        src = Path(source)
        dest = boot_path / src.name
        self.run_cmd(f"cp {src} {dest}", sudo=True)
        return {"method": "file", "path": str(dest),
                "installed": True, "boot_path": str(boot_path)}


@security.kernel.compile(require_root=True, cgroup_cpu=50, cgroup_mem=4096)
class KernelCompileTask(Task):
    """
    Compile un noyau depuis les sources.

    Params :
      - source_dir: str   Repertoire des sources kernel
      - config: str        Chemin d'un .config personnalise
      - jobs: int          Nombre de jobs paralleles
      - boot_path: str     Repertoire cible pour make install
    """

    executor = "threaded"

    def required_resources(self):
        return [KERNEL, Resource("system.cpu")]

    def required_locks(self):
        return [Lock("kernel", owner_id=str(self.id), exclusive=True)]

    def run(self) -> dict[str, Any]:
        source_dir = Path(self.params.get("source_dir", ""))
        config = self.params.get("config", "")
        jobs = self.params.get("jobs", os.cpu_count() or 4)

        if not source_dir or not source_dir.is_dir():
            raise FileNotFoundError(
                f"Kernel source not found: {source_dir}")

        # Config
        if config and Path(config).is_file():
            self.run_cmd(f"cp {config} {source_dir}/.config")
        elif not (source_dir / ".config").exists():
            self.run_cmd("make defconfig", cwd=source_dir)

        # Compile avec attachement cgroup si disponible
        cmd = ["make", f"-j{jobs}"]
        proc = None
        try:
            proc = subprocess.Popen(
                cmd,
                cwd=source_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            if hasattr(self, '_cgroup') and self._cgroup:
                self._cgroup.attach(proc.pid)
            stdout, stderr = proc.communicate(timeout=3600)
            if proc.returncode != 0:
                raise RuntimeError(
                    f"make failed with code {proc.returncode}: {stderr.decode()[:500]}"
                )
        except subprocess.TimeoutExpired:
            if proc:
                proc.kill()
                proc.communicate()
            raise TimeoutError(f"make timed out after 3600 seconds")
        self.run_cmd(
            "make modules_install", cwd=source_dir, sudo=True, timeout=600)
        self.run_cmd(
            "make install", cwd=source_dir, sudo=True, timeout=120)

        # Extraire la version
        r = self.run_cmd("make kernelversion", cwd=source_dir, check=False)
        version = r.stdout.strip()

        return {"version": version, "compiled": True,
                "source_dir": str(source_dir)}
