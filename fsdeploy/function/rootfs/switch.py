"""
fsdeploy.function.rootfs.switch
================================
Bascule de rootfs (overlay SquashFS + ZFS) à chaud.

Architecture overlay :
  - lower : SquashFS read-only (rootfs.sfs)
  - upper : ZFS dataset read-write (fast_pool/overlay-<system>)
  - merged : overlayfs combiné

Invariant : single dataset per system (fast_pool/overlay-<system>).
"""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Optional

from scheduler.model.task import Task
from scheduler.model.resource import Resource, ROOTFS
from scheduler.model.lock import Lock
from scheduler.security.decorator import security


def _is_mounted(path: str) -> bool:
    """Vérifie si un chemin est un point de montage."""
    path = os.path.realpath(path)
    with open("/proc/mounts", "r") as f:
        for line in f:
            parts = line.split()
            if len(parts) >= 2 and os.path.realpath(parts[1]) == path:
                return True
    return False


def _get_mount_source(path: str) -> Optional[str]:
    """Récupère la source d'un montage."""
    path = os.path.realpath(path)
    with open("/proc/mounts", "r") as f:
        for line in f:
            parts = line.split()
            if len(parts) >= 2 and os.path.realpath(parts[1]) == path:
                return parts[0]
    return None


@security.rootfs.mount(require_root=True)
class RootfsMountTask(Task):
    """
    Monte un rootfs overlay (squashfs + zfs upper).
    
    Params:
      - rootfs_sfs: chemin du squashfs
      - overlay_dataset: dataset ZFS pour l'upper (optionnel)
      - mount_base: répertoire de base pour les montages
      - target: point de montage final (défaut: /mnt/merged)
    """

    def required_resources(self):
        return [ROOTFS]

    def required_locks(self):
        return [Lock("rootfs", owner_id=str(self.id), exclusive=True)]

    def run(self) -> dict[str, Any]:
        rootfs_sfs = self.params.get("rootfs_sfs", "")
        overlay_dataset = self.params.get("overlay_dataset", "")
        mount_base = Path(self.params.get("mount_base", "/mnt"))
        target = Path(self.params.get("target", "/mnt/merged"))

        if not rootfs_sfs:
            raise ValueError("rootfs_sfs required")

        sfs_path = Path(rootfs_sfs)
        if not sfs_path.exists():
            raise FileNotFoundError(f"SquashFS not found: {rootfs_sfs}")

        results = {
            "rootfs_sfs": str(sfs_path),
            "overlay_dataset": overlay_dataset,
            "mounted": False,
        }

        # Créer les répertoires
        lower_dir = mount_base / "lower"
        upper_dir = mount_base / "upper"
        work_dir = mount_base / "work"

        for d in (lower_dir, upper_dir, work_dir, target):
            d.mkdir(parents=True, exist_ok=True)

        # 1. Monter le squashfs en lower
        if not _is_mounted(str(lower_dir)):
            self.run_cmd(
                f"mount -t squashfs -o loop,ro {sfs_path} {lower_dir}",
                sudo=True,
            )
        results["lower"] = str(lower_dir)

        # 2. Monter le dataset ZFS en upper (si spécifié)
        if overlay_dataset:
            if not _is_mounted(str(upper_dir)):
                self.run_cmd(
                    f"mount -t zfs {overlay_dataset} {upper_dir}",
                    sudo=True,
                )
            # Créer les sous-répertoires upper/work dans le dataset
            (upper_dir / "upper").mkdir(exist_ok=True)
            (upper_dir / "work").mkdir(exist_ok=True)
            upper_path = upper_dir / "upper"
            work_path = upper_dir / "work"
        else:
            # Upper en tmpfs si pas de dataset
            if not _is_mounted(str(upper_dir)):
                self.run_cmd(
                    f"mount -t tmpfs tmpfs {upper_dir}",
                    sudo=True,
                )
            (upper_dir / "upper").mkdir(exist_ok=True)
            (upper_dir / "work").mkdir(exist_ok=True)
            upper_path = upper_dir / "upper"
            work_path = upper_dir / "work"

        results["upper"] = str(upper_path)
        results["work"] = str(work_path)

        # 3. Assembler l'overlayfs
        if not _is_mounted(str(target)):
            self.run_cmd(
                f"mount -t overlay overlay "
                f"-o lowerdir={lower_dir},upperdir={upper_path},workdir={work_path} "
                f"{target}",
                sudo=True,
            )

        results["target"] = str(target)
        results["mounted"] = True

        return results


@security.rootfs.switch(require_root=True)
class RootfsSwitchTask(Task):
    """
    Bascule vers un nouveau rootfs.sfs + overlay dataset.
    
    Opération à chaud (système déjà booté).
    """

    def required_resources(self):
        return [ROOTFS]

    def required_locks(self):
        return [Lock("rootfs", owner_id=str(self.id), exclusive=True)]

    def run(self) -> dict[str, Any]:
        new_sfs = self.params.get("rootfs_sfs", "")
        new_overlay = self.params.get("overlay_dataset", "")
        mount_base = Path(self.params.get("mount_base", "/mnt"))
        keep_old = self.params.get("keep_old", True)

        if not new_sfs:
            raise ValueError("rootfs_sfs required")

        sfs_path = Path(new_sfs)
        if not sfs_path.exists():
            raise FileNotFoundError(f"SquashFS not found: {new_sfs}")

        results = {
            "old_rootfs": "",
            "new_rootfs": str(sfs_path),
            "switched": False,
        }

        # Récupérer l'ancien lower
        old_lower = mount_base / "lower"
        if _is_mounted(str(old_lower)):
            results["old_rootfs"] = _get_mount_source(str(old_lower)) or ""

        # Créer les nouveaux répertoires
        new_lower = mount_base / "new_lower"
        new_upper = mount_base / "new_upper"
        new_work = mount_base / "new_work"
        new_merged = mount_base / "new_merged"

        for d in (new_lower, new_upper, new_work, new_merged):
            d.mkdir(parents=True, exist_ok=True)

        # 1. Monter le nouveau squashfs
        self.run_cmd(
            f"mount -t squashfs -o loop,ro {sfs_path} {new_lower}",
            sudo=True,
        )

        # 2. Monter le nouveau dataset overlay
        if new_overlay:
            self.run_cmd(
                f"mount -t zfs {new_overlay} {new_upper}",
                sudo=True,
            )
            (new_upper / "upper").mkdir(exist_ok=True)
            (new_upper / "work").mkdir(exist_ok=True)
            upper_path = new_upper / "upper"
            work_path = new_upper / "work"
        else:
            self.run_cmd(f"mount -t tmpfs tmpfs {new_upper}", sudo=True)
            (new_upper / "upper").mkdir(exist_ok=True)
            (new_upper / "work").mkdir(exist_ok=True)
            upper_path = new_upper / "upper"
            work_path = new_upper / "work"

        # 3. Assembler le nouvel overlayfs
        self.run_cmd(
            f"mount -t overlay overlay "
            f"-o lowerdir={new_lower},upperdir={upper_path},workdir={work_path} "
            f"{new_merged}",
            sudo=True,
        )

        # 4. Pivot root (si demandé et possible)
        # Note : pivot_root nécessite que new_merged soit un mount point
        # et que / soit différent de new_merged
        do_pivot = self.params.get("pivot", False)
        if do_pivot:
            old_root = new_merged / ".old_root"
            old_root.mkdir(exist_ok=True)

            # Sauvegarder les montages essentiels
            for mp in ("/proc", "/sys", "/dev", "/run"):
                new_mp = new_merged / mp.lstrip("/")
                new_mp.mkdir(parents=True, exist_ok=True)
                self.run_cmd(f"mount --bind {mp} {new_mp}", sudo=True)

            # Pivot
            self.run_cmd(
                f"pivot_root {new_merged} {old_root}",
                sudo=True,
            )
            results["pivoted"] = True

        results["new_lower"] = str(new_lower)
        results["new_upper"] = str(upper_path)
        results["new_merged"] = str(new_merged)
        results["switched"] = True

        return results


@security.rootfs.update(require_root=True)
class RootfsUpdateTask(Task):
    """
    Met à jour le rootfs en place.
    
    Options :
      - sync_upper: synchronise l'upper vers un nouveau dataset
      - rebuild_sfs: reconstruit le squashfs depuis l'état actuel
      - clean_upper: nettoie l'upper layer
    """

    executor = "threaded"

    def required_resources(self):
        return [ROOTFS]

    def required_locks(self):
        return [Lock("rootfs", owner_id=str(self.id), exclusive=True)]

    def run(self) -> dict[str, Any]:
        action = self.params.get("action", "sync_upper")
        mount_base = Path(self.params.get("mount_base", "/mnt"))

        results = {
            "action": action,
            "completed": False,
        }

        if action == "sync_upper":
            results.update(self._sync_upper(mount_base))
        elif action == "rebuild_sfs":
            results.update(self._rebuild_sfs(mount_base))
        elif action == "clean_upper":
            results.update(self._clean_upper(mount_base))
        else:
            raise ValueError(f"Unknown action: {action}")

        return results

    def _sync_upper(self, mount_base: Path) -> dict:
        """Synchronise l'upper vers un nouveau dataset."""
        source_upper = mount_base / "upper" / "upper"
        target_dataset = self.params.get("target_dataset", "")

        if not source_upper.is_dir():
            raise FileNotFoundError(f"Source upper not found: {source_upper}")
        if not target_dataset:
            raise ValueError("target_dataset required for sync")

        # Créer le snapshot source
        src_dataset = self.params.get("source_dataset", "")
        if src_dataset:
            snap_name = f"{src_dataset}@pre-sync"
            self.run_cmd(f"zfs snapshot {snap_name}", sudo=True, check=False)

        # Monter le target
        target_mount = mount_base / "sync_target"
        target_mount.mkdir(parents=True, exist_ok=True)
        self.run_cmd(
            f"mount -t zfs {target_dataset} {target_mount}",
            sudo=True,
        )

        # Rsync
        self.run_cmd(
            f"rsync -aHAX --delete {source_upper}/ {target_mount}/",
            sudo=True,
            timeout=3600,
        )

        # Démonter
        self.run_cmd(f"umount {target_mount}", sudo=True)

        return {
            "completed": True,
            "synced_to": target_dataset,
        }

    def _rebuild_sfs(self, mount_base: Path) -> dict:
        """Reconstruit le squashfs depuis l'état merged actuel."""
        merged = mount_base / "merged"
        output = Path(self.params.get("output", "/tmp/rootfs-new.sfs"))
        compress = self.params.get("compress", "zstd")

        if not merged.is_dir() or not _is_mounted(str(merged)):
            raise FileNotFoundError("Merged rootfs not mounted")

        # Construire le squashfs
        comp_opts = {
            "zstd": "-comp zstd -Xcompression-level 19",
            "xz": "-comp xz -Xbcj x86",
            "gzip": "-comp gzip",
            "lz4": "-comp lz4 -Xhc",
        }.get(compress, f"-comp {compress}")

        self.run_cmd(
            f"mksquashfs {merged} {output} {comp_opts} -noappend",
            sudo=True,
            timeout=3600,
        )

        return {
            "completed": True,
            "output": str(output),
            "size": output.stat().st_size if output.exists() else 0,
        }

    def _clean_upper(self, mount_base: Path) -> dict:
        """Nettoie l'upper layer (supprime les fichiers modifiés)."""
        upper = mount_base / "upper" / "upper"

        if not upper.is_dir():
            raise FileNotFoundError(f"Upper not found: {upper}")

        # Compter les fichiers avant
        count_before = sum(1 for _ in upper.rglob("*") if _.is_file())

        # Nettoyer (supprimer tout sauf les whiteouts)
        for item in upper.iterdir():
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()

        return {
            "completed": True,
            "files_removed": count_before,
        }


@security.rootfs.umount(require_root=True)
class RootfsUmountTask(Task):
    """Démonte le rootfs overlay."""

    def required_locks(self):
        return [Lock("rootfs", owner_id=str(self.id), exclusive=True)]

    def run(self) -> dict[str, Any]:
        mount_base = Path(self.params.get("mount_base", "/mnt"))
        force = self.params.get("force", False)

        results = {"unmounted": []}

        # Ordre de démontage : merged, upper, lower
        for subdir in ("merged", "new_merged", "upper", "new_upper", "lower", "new_lower"):
            mp = mount_base / subdir
            if mp.exists() and _is_mounted(str(mp)):
                flag = "-l" if force else ""
                self.run_cmd(f"umount {flag} {mp}", sudo=True, check=False)
                results["unmounted"].append(str(mp))

        return results


# Re-exports
__all__ = [
    "RootfsMountTask",
    "RootfsSwitchTask",
    "RootfsUpdateTask",
    "RootfsUmountTask",
]
