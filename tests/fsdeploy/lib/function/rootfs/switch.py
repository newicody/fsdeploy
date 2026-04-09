"""
fsdeploy.function.rootfs.switch
================================
Bascule de rootfs (overlay SquashFS + ZFS) à chaud.

Invariant : single dataset per system (fast_pool/overlay-<system>).
"""

import shutil
from pathlib import Path
from typing import Any

from scheduler.model.task import Task
from scheduler.model.resource import Resource, ROOTFS
from scheduler.model.lock import Lock
from scheduler.security.decorator import security


@security.rootfs.switch(require_root=True)
class RootfsSwitchTask(Task):
    """
    Bascule vers un nouveau rootfs.sfs + overlay dataset.
    """

    def required_resources(self):
        return [ROOTFS]

    def required_locks(self):
        return [Lock("rootfs", owner_id=str(self.id), exclusive=True)]

    def run(self) -> dict[str, Any]:
        new_sfs = self.params.get("rootfs_sfs", "")
        new_overlay = self.params.get("overlay_dataset", "")
        mount_base = self.params.get("mount_base", "/mnt")

        if not new_sfs:
            raise ValueError("rootfs_sfs required")

        sfs_path = Path(new_sfs)
        if not sfs_path.exists():
            raise FileNotFoundError(f"SquashFS not found: {new_sfs}")

        results = {"old_rootfs": "", "new_rootfs": str(sfs_path), "switched": False}

        # 1. Monter le nouveau squashfs en lower
        new_lower = Path(mount_base) / "new_lower"
        new_lower.mkdir(parents=True, exist_ok=True)
        self.run_cmd(
            f"mount -t squashfs -o loop,ro {sfs_path} {new_lower}",
            sudo=True,
        )

        # 2. Monter le dataset overlay
        if new_overlay:
            new_upper = Path(mount_base) / "new_upper"
            new_upper.mkdir(parents=True, exist_ok=True)
            self.run_cmd(
                f"mount -t zfs {new_overlay} {new_upper}",
                sudo=True,
            )
            # S'assurer des sous-répertoires
            (new_upper / "upper").mkdir(exist_ok=True)
            (new_upper / "work").mkdir(exist_ok=True)

        # 3. Assembler l'overlayfs
        merged = Path(mount_base) / "new_merged"
        merged.mkdir(parents=True, exist_ok=True)

        if new_overlay:
            upper_dir = f"{mount_base}/new_upper/upper"
            work_dir = f"{mount_base}/new_upper/work"
        else:
            # Tmpfs comme upper (volatile)
            tmp_upper = Path(mount_base) / "tmp_upper"
            tmp_upper.mkdir(parents=True, exist_ok=True)
            self.run_cmd(f"mount -t tmpfs tmpfs {tmp_upper}", sudo=True)
            (tmp_upper / "upper").mkdir(exist_ok=True)
            (tmp_upper / "work").mkdir(exist_ok=True)
            upper_dir = f"{tmp_upper}/upper"
            work_dir = f"{tmp_upper}/work"

        self.run_cmd(
            f"mount -t overlay overlay "
            f"-o lowerdir={new_lower},upperdir={upper_dir},workdir={work_dir} "
            f"{merged}",
            sudo=True,
        )

        results["switched"] = True
        results["merged"] = str(merged)

        return results


@security.rootfs.mount(require_root=True)
class RootfsMountTask(Task):
    """Monte un rootfs existant (squashfs + overlay)."""

    def required_resources(self):
        return [ROOTFS]

    def run(self) -> dict[str, Any]:
        sfs_path = self.params.get("rootfs_sfs", "")
        overlay_dataset = self.params.get("overlay_dataset", "")
        mountpoint = self.params.get("mountpoint", "/mnt/rootfs")

        if not sfs_path:
            raise ValueError("rootfs_sfs required")

        mp = Path(mountpoint)
        lower = mp / "lower"
        upper = mp / "upper"
        merged = mp / "merged"

        for d in (lower, upper, merged):
            d.mkdir(parents=True, exist_ok=True)

        # Lower
        self.run_cmd(f"mount -t squashfs -o loop,ro {sfs_path} {lower}", sudo=True)

        # Upper
        if overlay_dataset:
            self.run_cmd(f"mount -t zfs {overlay_dataset} {upper}", sudo=True)
        else:
            self.run_cmd(f"mount -t tmpfs tmpfs {upper}", sudo=True)

        (upper / "upper").mkdir(exist_ok=True)
        (upper / "work").mkdir(exist_ok=True)

        # Merged
        self.run_cmd(
            f"mount -t overlay overlay "
            f"-o lowerdir={lower},upperdir={upper}/upper,workdir={upper}/work "
            f"{merged}",
            sudo=True,
        )

        return {"mountpoint": str(merged), "mounted": True}


@security.rootfs.update(require_root=True)
class RootfsUpdateTask(Task):
    """Met à jour le rootfs squashfs à partir du merged actuel."""

    def required_resources(self):
        return [ROOTFS]

    def required_locks(self):
        return [Lock("rootfs", owner_id=str(self.id), exclusive=True)]

    def run(self) -> dict[str, Any]:
        source = self.params.get("source", "/mnt/rootfs/merged")
        output = self.params.get("output", "/boot/images/rootfs.sfs")
        compress = self.params.get("compress", "zstd")
        exclude = self.params.get("exclude", [
            "proc", "sys", "dev", "run", "tmp", "mnt",
            "var/cache", "var/log", "var/tmp",
        ])

        exclude_args = " ".join(f"-e {e}" for e in exclude)

        self.run_cmd(
            f"mksquashfs {source} {output}.new -comp {compress} -noappend {exclude_args}",
            sudo=True, timeout=600,
        )

        # Remplacement atomique
        output_path = Path(output)
        new_path = Path(f"{output}.new")
        if output_path.exists():
            output_path.rename(f"{output}.bak")
        new_path.rename(output_path)

        return {
            "output": str(output_path),
            "size": output_path.stat().st_size,
            "updated": True,
        }
