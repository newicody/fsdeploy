# -*- coding: utf-8 -*-
"""
fsdeploy.intents.detection_intent
===================================
Intents pour la detection, le montage et le demontage.

Chaque event est converti en Intent par @register_intent.
L'Intent produit des Tasks qui s'executent dans le scheduler.
"""

from typing import Any

from scheduler.model.intent import Intent
from scheduler.model.task import Task
from scheduler.model.resource import Resource
from scheduler.model.lock import Lock
from scheduler.core.registry import register_intent
from scheduler.security.decorator import security


# ===================================================================
# TABLE DE MOTIFS
# ===================================================================

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


# ===================================================================
# TASKS
# ===================================================================

@security.detect.probe
class PoolImportAllTask(Task):
    """
    Importe les pools disponibles AVANT la detection.

    IMPORTANT : ne pas utiliser 'zpool import -af' aveugle car si les
    pools sont deja importes, la commande peut bloquer ou echouer.
    On liste d'abord les pools importables, puis on importe seulement
    ceux qui ne le sont pas encore.
    """

    def run(self) -> dict[str, Any]:
        # 1. Lister les pools DEJA importes
        r_existing = self.run_cmd(
            "zpool list -H -o name", sudo=True, check=False)
        already = set()
        if r_existing.success:
            already = {p.strip() for p in r_existing.stdout.splitlines()
                       if p.strip()}

        # 2. Lister les pools IMPORTABLES (pas encore importes)
        r_avail = self.run_cmd("zpool import", sudo=True, check=False)
        importable = []
        for line in r_avail.stdout.splitlines():
            line = line.strip()
            if line.startswith("pool:"):
                name = line.split(":", 1)[1].strip()
                if name not in already:
                    importable.append(name)

        # 3. Importer un par un (pas -a qui bloque si conflit)
        imported = []
        for pool in importable:
            r = self.run_cmd(
                f"zpool import -f -N -o cachefile=none {pool}",
                sudo=True, check=False, timeout=30)
            if r.success:
                imported.append(pool)

        # 4. Liste finale
        r_final = self.run_cmd(
            "zpool list -H -o name", sudo=True, check=False)
        all_pools = [p.strip() for p in r_final.stdout.splitlines()
                     if p.strip()]

        return {
            "imported_pools": all_pools,
            "newly_imported": imported,
            "already_imported": list(already),
        }


@security.detect.probe
class DatasetProbeTask(Task):
    """Inspecte le contenu d'un dataset pour determiner son role."""

    def required_locks(self):
        ds = self.params.get("dataset", "")
        pool = ds.split("/")[0] if "/" in ds else ds
        return [Lock(f"pool.{pool}", owner_id=str(self.id))]

    def _probe_in_namespace(self, dataset, scan_path):
        """
        Probe dans un mount namespace isole.
        Le mount est auto-nettoye si le processus crash.
        Fallback sur probe direct si unshare indisponible.
        """
        import multiprocessing
        import os as _os

        # Verifier que os.unshare est disponible (Python 3.12+)
        if not hasattr(_os, 'unshare'):
            return None  # fallback

        result_queue = multiprocessing.Queue()

        def _child(dataset, scan_path_str, queue):
            try:
                import os as child_os
                from pathlib import Path
                import subprocess

                # Entrer dans un mount namespace isole
                try:
                    child_os.unshare(child_os.CLONE_NEWNS)
                except (OSError, AttributeError):
                    queue.put(None)  # fallback
                    return

                # Rendre les mounts prives
                subprocess.run(
                    ["mount", "--make-rprivate", "/"],
                    capture_output=True, timeout=5,
                )

                sp = Path(scan_path_str)
                sp.mkdir(parents=True, exist_ok=True)

                # Monter
                r = subprocess.run(
                    ["mount", "-t", "zfs", dataset, scan_path_str],
                    capture_output=True, text=True, timeout=30,
                )
                if r.returncode != 0:
                    queue.put({
                        "dataset": dataset, "role": "unknown",
                        "confidence": 0, "error": r.stderr,
                    })
                    return

                # Scanner (reimplemente ici car on est dans un fork)
                from fsdeploy.lib.function.detect.role_patterns import (
                    ROLE_PATTERNS, score_patterns,
                )
                role, confidence, details = score_patterns(sp)
                queue.put({
                    "dataset": dataset, "role": role,
                    "confidence": confidence, "details": details,
                })
                # Pas besoin de umount — le namespace meurt avec le process

            except Exception as e:
                queue.put({
                    "dataset": dataset, "role": "unknown",
                    "confidence": 0, "error": str(e),
                })

        proc = multiprocessing.Process(
            target=_child,
            args=(dataset, str(scan_path), result_queue),
        )
        proc.start()
        proc.join(timeout=60)

        if proc.is_alive():
            proc.kill()
            proc.join(timeout=5)
            return {
                "dataset": dataset, "role": "unknown",
                "confidence": 0, "error": "timeout",
            }

        try:
            return result_queue.get_nowait()
        except Exception:
            return None  # fallback

    def run(self) -> dict[str, Any]:
        import tempfile
        from pathlib import Path

        dataset = self.params.get("dataset", "")
        mountpoint = self.params.get("mountpoint", "")
        is_mounted = self.params.get("mounted", False)

        if not dataset:
            return {"dataset": "", "role": "unknown", "confidence": 0}

        # Si deja monte, scanner directement
        if is_mounted and mountpoint and mountpoint not in ("-", "none"):
            scan_path = Path(mountpoint)
        else:
            # Essayer avec mount namespace (anti-leak)
            scan_path = Path(tempfile.mkdtemp(prefix="fsdeploy-probe-"))
            ns_result = self._probe_in_namespace(dataset, scan_path)
            if ns_result is not None:
                try:
                    scan_path.rmdir()
                except OSError:
                    pass
                return ns_result

            # Fallback : montage direct (sans namespace)
            r = self.run_cmd(
                f"mount -t zfs {dataset} {scan_path}",
                sudo=True, check=False, timeout=30)
            if not r.success:
                try:
                    scan_path.rmdir()
                except OSError:
                    pass
                return {"dataset": dataset, "role": "unknown",
                        "confidence": 0, "error": r.stderr}

        try:
            role, confidence, details = self._scan(scan_path)
            return {"dataset": dataset, "role": role,
                    "confidence": confidence, "details": details}
        finally:
            if not is_mounted:
                self.run_cmd(f"umount {scan_path}",
                             sudo=True, check=False)
                try:
                    scan_path.rmdir()
                except OSError:
                    pass

    def _scan(self, path):
        """Scan le contenu et retourne (role, confidence, details)."""
        from pathlib import Path

        best_role = "data"
        best_score = 0
        best_prio = -1
        details = {}

        for pattern in ROLE_PATTERNS:
            matches = 0
            matched_globs = []
            for g in pattern["globs"]:
                found = list(path.glob(g))
                if found:
                    matches += 1
                    matched_globs.append(g)

            if matches >= pattern["min"]:
                score = matches / len(pattern["globs"])
                prio = pattern["prio"]
                if prio > best_prio or (prio == best_prio and score > best_score):
                    best_role = pattern["role"]
                    best_score = score
                    best_prio = prio
                    details = {"matched": matched_globs, "count": matches}

        return best_role, best_score, details


@security.detect.probe
class PartitionDetectTask(Task):
    """Detecte les partitions du systeme."""

    def run(self) -> list[dict]:
        r = self.run_cmd("lsblk -J -o NAME,FSTYPE,LABEL,UUID,SIZE,MOUNTPOINT",
                         sudo=True, check=False)
        if not r.success:
            return []

        import json
        partitions = []
        try:
            data = json.loads(r.stdout)
            for dev in data.get("blockdevices", []):
                self._extract_partitions(dev, partitions)
        except (json.JSONDecodeError, KeyError):
            pass

        return partitions

    def _extract_partitions(self, dev, result):
        name = dev.get("name", "")
        fstype = dev.get("fstype")
        if fstype and fstype not in ("", "zfs_member"):
            role = "unknown"
            if fstype in ("vfat", "fat32"):
                role = "efi"
            elif fstype == "swap":
                role = "swap"
            result.append({
                "device": f"/dev/{name}",
                "fstype": fstype or "",
                "label": dev.get("label", "") or "",
                "uuid": dev.get("uuid", "") or "",
                "size": dev.get("size", "") or "",
                "mountpoint": dev.get("mountpoint", "") or "",
                "role": role,
            })
        for child in dev.get("children", []):
            self._extract_partitions(child, result)


@security.mount.verify
class MountVerifyTask(Task):
    """Verifie qu'un dataset est monte au bon endroit."""

    def run(self) -> dict[str, Any]:
        dataset = self.params.get("dataset", "")
        mountpoint = self.params.get("mountpoint", "")
        from pathlib import Path

        try:
            mounts = Path("/proc/mounts").read_text()
            for line in mounts.splitlines():
                parts = line.split()
                if len(parts) >= 2 and parts[0] == dataset:
                    actual = parts[1]
                    return {"dataset": dataset, "verified": actual == mountpoint,
                            "actual": actual, "expected": mountpoint}
        except OSError:
            pass

        return {"dataset": dataset, "verified": False, "error": "not mounted"}


@security.mount.umount
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


# ===================================================================
# INTENTS
# ===================================================================

@register_intent("pool.import_all")
class PoolImportAllIntent(Intent):
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
    """Import + pools + partitions."""
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
