"""
fsdeploy.function.boot.initramfs
==================================
Construction de l'initramfs via dracut ou cpio custom.

Modes :
  - dracut : utilise dracut avec les modules ZBM
  - cpio   : construit manuellement un initramfs cpio
"""

import os
import shutil
from pathlib import Path
from typing import Any

from scheduler.model.task import Task
from scheduler.model.resource import Resource, INITRAMFS, KERNEL
from scheduler.model.lock import Lock
from scheduler.security.decorator import security


@security.boot.initramfs(require_root=True)
class InitramfsBuildTask(Task):
    """
    Construit un initramfs pour un noyau donné.
    """

    def required_resources(self):
        return [INITRAMFS]

    def required_locks(self):
        return [Lock("initramfs", owner_id=str(self.id))]

    def run(self) -> dict[str, Any]:
        method = self.params.get("method", "dracut")
        kernel_version = self.params.get("kernel_version", "")
        compress = self.params.get("compress", "zstd")
        output_path = self.params.get("output", "")
        init_type = self.params.get("init_type", "zbm")
        extra_drivers = self.params.get("extra_drivers", [])
        extra_modules = self.params.get("extra_modules", [])
        force = self.params.get("force", False)

        if not kernel_version:
            kernel_version = self._detect_kernel_version()
        if not output_path:
            output_path = f"/boot/initramfs-{kernel_version}.img"

        output = Path(output_path)
        if output.exists() and not force:
            return {"status": "exists", "path": str(output)}

        if method == "dracut":
            return self._build_dracut(
                kernel_version, output, compress,
                init_type, extra_drivers, extra_modules,
            )
        elif method == "cpio":
            return self._build_cpio(kernel_version, output, compress, init_type)
        else:
            raise ValueError(f"Unknown method: {method}")

    def _build_dracut(self, kver: str, output: Path, compress: str,
                      init_type: str, extra_drivers: list, extra_modules: list) -> dict:
        """Construit via dracut."""
        cmd_parts = [
            "dracut", "--force", "--kver", kver,
            "--compress", compress,
        ]

        # Modules dracut
        base_modules = ["zfs", "base", "rootfs-block", "kernel-modules"]
        if init_type == "zbm":
            base_modules.append("zfsbootmenu")
        if init_type == "stream":
            base_modules.extend(["network", "ifcfg", "url-lib"])

        for mod in base_modules + extra_modules:
            cmd_parts.extend(["--add", mod])

        for drv in extra_drivers:
            cmd_parts.extend(["--add-drivers", drv])

        # Init custom si pas zbm
        if init_type in ("minimal", "stream"):
            init_file = self.params.get("init_file", "")
            if init_file and Path(init_file).exists():
                cmd_parts.extend(["--include", init_file, "/init"])

        cmd_parts.append(str(output))

        result = self.run_cmd(cmd_parts, sudo=True, timeout=300)

        return {
            "status": "built",
            "method": "dracut",
            "path": str(output),
            "kernel": kver,
            "compress": compress,
            "size": output.stat().st_size if output.exists() else 0,
        }

    def _build_cpio(self, kver: str, output: Path, compress: str,
                    init_type: str) -> dict:
        """Construit un initramfs minimal via cpio."""
        workdir = Path(f"/tmp/fsdeploy-initramfs-{kver}")
        if workdir.exists():
            shutil.rmtree(workdir)

        # Structure de base
        for d in ("bin", "sbin", "usr/bin", "usr/sbin", "lib", "lib64",
                  "etc", "dev", "proc", "sys", "run", "tmp",
                  "mnt/boot", "mnt/lower", "mnt/upper", "mnt/merged"):
            (workdir / d).mkdir(parents=True, exist_ok=True)

        # Copier les binaires essentiels
        essentials = ["/bin/sh", "/bin/busybox", "/sbin/zpool", "/sbin/zfs",
                     "/sbin/mount", "/sbin/umount", "/bin/mount", "/sbin/modprobe",
                     "/sbin/pivot_root"]
        for binary in essentials:
            if Path(binary).exists():
                dest = workdir / binary.lstrip("/")
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(binary, dest)
                # Copier les libs dynamiques
                self._copy_libs(binary, workdir)

        # Modules kernel
        modules_src = Path(f"/lib/modules/{kver}")
        if modules_src.exists():
            modules_dst = workdir / f"lib/modules/{kver}"
            shutil.copytree(modules_src, modules_dst, dirs_exist_ok=True)

        # Init script
        init_file = self.params.get("init_file", "")
        if init_file and Path(init_file).exists():
            shutil.copy2(init_file, workdir / "init")
        else:
            (workdir / "init").write_text("#!/bin/sh\nexec /bin/sh\n")
        (workdir / "init").chmod(0o755)

        # Créer le cpio
        compress_cmd = {"zstd": "zstd -T0", "xz": "xz -T0", "gzip": "gzip", "lz4": "lz4"}
        pipe = compress_cmd.get(compress, "zstd -T0")

        self.run_cmd(
            f"bash -c 'cd {workdir} && find . | cpio -o -H newc 2>/dev/null | {pipe} > {output}'",
            sudo=True, timeout=120,
        )

        # Cleanup
        shutil.rmtree(workdir, ignore_errors=True)

        return {
            "status": "built",
            "method": "cpio",
            "path": str(output),
            "kernel": kver,
            "compress": compress,
            "size": output.stat().st_size if output.exists() else 0,
        }

    def _copy_libs(self, binary: str, workdir: Path) -> None:
        """Copie les bibliothèques dynamiques nécessaires."""
        result = self.run_cmd(f"ldd {binary}", check=False, capture=True)
        if not result.success:
            return
        for line in result.stdout.splitlines():
            parts = line.strip().split()
            for part in parts:
                if part.startswith("/") and Path(part).is_file():
                    dest = workdir / part.lstrip("/")
                    if not dest.exists():
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(part, dest)

    def _detect_kernel_version(self) -> str:
        """Détecte la version du noyau courant."""
        result = self.run_cmd("uname -r", check=False)
        return result.stdout.strip() if result.success else ""
