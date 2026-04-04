"""
fsdeploy.intents.detection_intent
===================================
Intents pour toutes les operations declenchees par la TUI via le bus.

Chaque event est converti en Intent par @register_intent.
L'Intent produit des Tasks qui s'executent dans le scheduler
avec locks, security, et logging.
"""

from typing import Any

from scheduler.model.intent import Intent
from scheduler.model.task import Task
from scheduler.model.resource import Resource
from scheduler.model.lock import Lock
from scheduler.core.registry import register_intent
from scheduler.security.decorator import security


# ═══════════════════════════════════════════════════════════════════
# TABLE DE MOTIFS — detection du role par contenu
# ═══════════════════════════════════════════════════════════════════

ROLE_PATTERNS = [
    {"role": "boot",       "globs": ["vmlinuz*", "bzImage*", "initramfs*",
     "initrd*", "EFI/**", "efi/**", "fsdeploy.conf"],
     "min": 2, "prio": 10},
    {"role": "kernel",     "globs": ["vmlinuz*", "bzImage*", "config-*",
     "System.map-*"], "min": 1, "prio": 8},
    {"role": "modules",    "globs": ["lib/modules/*/modules.dep",
     "lib/modules/*/*.ko", "lib/modules/*/*.ko.zst", "modules-*.sfs"],
     "min": 1, "prio": 7},
    {"role": "initramfs",  "globs": ["initramfs*.img", "initrd.img-*"],
     "min": 1, "prio": 6},
    {"role": "rootfs",     "globs": ["etc/os-release", "usr/bin/*",
     "sbin/*", "etc/fstab"], "min": 2, "prio": 5},
    {"role": "squashfs",   "globs": ["*.sfs", "*.squashfs", "images/*.sfs"],
     "min": 1, "prio": 4},
    {"role": "efi",        "globs": ["EFI/BOOT/BOOTX64.EFI",
     "EFI/ZBM/*.EFI"], "min": 1, "prio": 9},
    {"role": "python_env", "globs": ["bin/python3", "lib/python3*"],
     "min": 2, "prio": 3},
    {"role": "overlay",    "globs": ["upper/", "work/"],
     "min": 2, "prio": 2},
    {"role": "data",       "globs": ["*"], "min": 1, "prio": 0},
]


# ═══════════════════════════════════════════════════════════════════
# TASKS
# ═══════════════════════════════════════════════════════════════════

@security.detect.probe
class PoolImportAllTask(Task):
    """Importe tous les pools avec -af -N avant detection."""

    def run(self) -> dict[str, Any]:
        r_import = self.run_cmd(
            "zpool import -af -N -o cachefile=none",
            sudo=True, check=False,
        )
        r_list = self.run_cmd("zpool list -H -o name", sudo=True, check=False)
        pools = [p.strip() for p in r_list.stdout.splitlines() if p.strip()]
        return {
            "imported_pools": pools,
            "import_output": r_import.stdout,
            "import_errors": r_import.stderr if not r_import.success else "",
        }


@security.detect.probe
class DatasetProbeTask(Task):
    """Inspecte le contenu d'un dataset pour determiner son role."""

    def required_locks(self):
        ds = self.params.get("dataset", "")
        pool = ds.split("/")[0] if "/" in ds else ds
        return [Lock(f"pool.{pool}.probe", owner_id=str(self.id),
                     exclusive=False)]

    def run(self) -> dict[str, Any]:
        import tempfile
        from pathlib import Path

        dataset = self.params.get("dataset", "")
        mountpoint = self.params.get("mountpoint", "")
        already_mounted = self.params.get("mounted", False)

        if not dataset:
            raise ValueError("dataset required")

        probe_path = None
        temp_mount = None

        if (already_mounted and mountpoint and mountpoint not in ("-", "none")
                and Path(mountpoint).is_dir()):
            probe_path = Path(mountpoint)
        else:
            temp_mount = tempfile.mkdtemp(prefix="fsdeploy-probe-")
            self.run_cmd(f"mount -t zfs {dataset} {temp_mount}",
                         sudo=True, check=False)
            try:
                if any(Path(temp_mount).iterdir()):
                    probe_path = Path(temp_mount)
            except PermissionError:
                pass

        if probe_path is None:
            self._cleanup(temp_mount)
            return {"dataset": dataset, "role": "empty",
                    "confidence": 0.0, "details": "vide ou non montable"}

        best = {"role": "data", "score": 0.0, "details": "", "prio": -1}
        try:
            for pat in ROLE_PATTERNS:
                matches = [g for g in pat["globs"]
                           if list(probe_path.glob(g))[:20]]
                if len(matches) >= pat["min"]:
                    score = min(len(matches) / max(len(pat["globs"]), 1), 1.0)
                    if (pat["prio"] > best["prio"] or
                            (pat["prio"] == best["prio"]
                             and score > best["score"])):
                        best = {"role": pat["role"], "score": score,
                                "details": ", ".join(matches[:5]),
                                "prio": pat["prio"]}
        except Exception as e:
            best["details"] = str(e)

        self._cleanup(temp_mount)
        return {"dataset": dataset, "role": best["role"],
                "confidence": best["score"], "details": best["details"]}

    def _cleanup(self, temp_mount):
        if temp_mount:
            self.run_cmd(f"umount {temp_mount}", sudo=True, check=False)
            import os
            try:
                os.rmdir(temp_mount)
            except OSError:
                pass


@security.detect.partitions
class PartitionDetectTask(Task):
    """Detecte les partitions via lsblk."""

    def run(self) -> list[dict[str, str]]:
        r = self.run_cmd("lsblk -ln -o NAME,FSTYPE,LABEL,UUID,SIZE,TYPE",
                         check=False)
        partitions = []
        for line in r.stdout.strip().splitlines():
            p = line.split(None, 5)
            if len(p) < 6 or p[5] != "part":
                continue
            role = ""
            if p[1] in ("vfat", "fat32"):
                role = "efi"
            elif p[1] == "swap":
                role = "swap"
            elif p[2] and "boot" in p[2].lower():
                role = "boot"
            elif "zfs" in p[1].lower():
                role = "zfs"
            partitions.append({"device": f"/dev/{p[0]}", "fstype": p[1] or "-",
                               "label": p[2] or "-", "uuid": p[3] or "-",
                               "size": p[4], "role": role})
        return partitions


@security.mount.verify
class MountVerifyTask(Task):
    """Verifie qu'un dataset est bien monte au bon endroit."""

    def run(self) -> dict[str, Any]:
        from pathlib import Path

        dataset = self.params.get("dataset", "")
        mountpoint = self.params.get("mountpoint", "")

        if not dataset or not mountpoint:
            return {"dataset": dataset, "verified": False,
                    "error": "dataset and mountpoint required"}

        try:
            mounts = Path("/proc/mounts").read_text()
            for line in mounts.splitlines():
                parts = line.split()
                if len(parts) >= 2 and parts[0] == dataset:
                    actual = parts[1]
                    verified = actual == mountpoint
                    return {"dataset": dataset, "mountpoint": actual,
                            "expected": mountpoint, "verified": verified}
        except OSError:
            pass

        r = self.run_cmd(f"zfs get -H -o value mountpoint {dataset}",
                         check=False)
        if r.success:
            mp = r.stdout.strip()
            if mp and mp not in ("-", "none"):
                r2 = self.run_cmd(f"mountpoint -q {mp}", check=False)
                verified = r2.success and mp == mountpoint
                return {"dataset": dataset, "mountpoint": mp,
                        "expected": mountpoint, "verified": verified}

        return {"dataset": dataset, "verified": False, "error": "not mounted"}


@security.mount.umount(require_root=True)
class UmountDatasetTask(Task):
    """Demonte un dataset."""

    def required_locks(self):
        ds = self.params.get("dataset", "")
        pool = ds.split("/")[0] if "/" in ds else ds
        return [Lock(f"pool.{pool}", owner_id=str(self.id))]

    def run(self) -> dict[str, Any]:
        dataset = self.params.get("dataset", "")
        mountpoint = self.params.get("mountpoint", "")
        target = mountpoint or dataset
        if not target:
            raise ValueError("dataset or mountpoint required")
        self.run_cmd(f"umount {target}", sudo=True, check=False)
        return {"dataset": dataset, "mountpoint": mountpoint,
                "unmounted": True}


# ═══════════════════════════════════════════════════════════════════
# INTENTS
# ═══════════════════════════════════════════════════════════════════

@register_intent("pool.import_all")
class PoolImportAllIntent(Intent):
    """Event: pool.import_all → PoolImportAllTask"""
    def build_tasks(self):
        return [PoolImportAllTask(
            id="import_all", params={}, context=self.context)]

@register_intent("pool.status")
class PoolStatusIntent(Intent):
    def build_tasks(self):
        from function.pool.status import PoolStatusTask
        return [PoolStatusTask(
            id="pool_status", params=self.params, context=self.context)]

@register_intent("pool.import")
class PoolImportIntent(Intent):
    def build_tasks(self):
        from function.pool.status import PoolImportTask
        pool = self.params.get("pool", "")
        if not pool:
            return []
        return [PoolImportTask(
            id=f"import_{pool}",
            params={"pool": pool, "force": True, "no_mount": True},
            context=self.context)]

@register_intent("dataset.list")
class DatasetListIntent(Intent):
    def build_tasks(self):
        from function.dataset.mount import DatasetListTask
        return [DatasetListTask(
            id=f"list_{self.params.get('pool', 'all')}",
            params=self.params, context=self.context)]

@register_intent("detection.partitions")
class PartitionDetectIntent(Intent):
    def build_tasks(self):
        return [PartitionDetectTask(
            id="detect_partitions", params={}, context=self.context)]

@register_intent("detection.probe_datasets")
class DetectionProbeIntent(Intent):
    def build_tasks(self):
        datasets = self.params.get("datasets", [])
        return [
            DatasetProbeTask(
                id=f"probe_{ds['name'].replace('/', '_')}",
                params={"dataset": ds["name"],
                        "mountpoint": ds.get("mountpoint", ""),
                        "mounted": ds.get("mounted", False)},
                context=self.context)
            for ds in datasets
        ]

@register_intent("detection.start")
class DetectionFullIntent(Intent):
    """Import + pools + partitions. TUI enchaine phases 2 et 3."""
    def build_tasks(self):
        from function.pool.status import PoolStatusTask
        tasks = [
            PoolImportAllTask(id="import_all", params={}, context=self.context),
            PoolStatusTask(id="detect_pools", params={}, context=self.context),
            PartitionDetectTask(id="detect_parts", params={}, context=self.context),
        ]
        pools = self.params.get("pools", [])
        if pools:
            from function.dataset.mount import DatasetListTask
            for pool in pools:
                tasks.append(DatasetListTask(
                    id=f"list_{pool}", params={"pool": pool},
                    context=self.context))
        return tasks

@register_intent("mount.request")
class MountRequestIntent(Intent):
    def build_tasks(self):
        from function.dataset.mount import DatasetMountTask
        ds = self.params.get("dataset", "")
        mp = self.params.get("mountpoint", "")
        if not ds or not mp:
            return []
        return [DatasetMountTask(
            id=f"mount_{ds.replace('/', '_')}",
            params={"dataset": ds, "mountpoint": mp},
            context=self.context)]

@register_intent("mount.umount")
class UmountRequestIntent(Intent):
    def build_tasks(self):
        ds = self.params.get("dataset", "")
        mp = self.params.get("mountpoint", "")
        return [UmountDatasetTask(
            id=f"umount_{ds.replace('/', '_')}",
            params={"dataset": ds, "mountpoint": mp},
            context=self.context)]

@register_intent("mount.verify")
class VerifyMountIntent(Intent):
    def build_tasks(self):
        return [MountVerifyTask(
            id=f"verify_{self.params.get('dataset', '').replace('/', '_')}",
            params=self.params, context=self.context)]
