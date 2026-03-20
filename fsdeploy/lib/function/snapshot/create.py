"""
fsdeploy.function.snapshot.create
==================================
Opérations sur les snapshots ZFS : create, rollback, send/receive.
"""

import time
from typing import Any

from scheduler.model.task import Task
from scheduler.model.resource import Resource, dataset_resource
from scheduler.model.lock import Lock
from scheduler.security.decorator import security


@security.dataset.snapshot.create
class SnapshotCreateTask(Task):
    """Crée un snapshot ZFS."""

    def required_locks(self):
        ds = self.params.get("dataset", "")
        return [Lock(f"dataset.{ds.replace('/', '.')}.snapshot", owner_id=str(self.id))]

    def run(self) -> dict[str, Any]:
        dataset = self.params.get("dataset", "")
        name = self.params.get("name", "")
        recursive = self.params.get("recursive", False)

        if not dataset:
            raise ValueError("dataset required")
        if not name:
            name = time.strftime("fsdeploy-%Y%m%d-%H%M%S")

        snapshot = f"{dataset}@{name}"
        cmd_parts = ["zfs", "snapshot"]
        if recursive:
            cmd_parts.append("-r")
        cmd_parts.append(snapshot)

        self.run_cmd(cmd_parts, sudo=True)

        return {"snapshot": snapshot, "created": True}


@security.dataset.snapshot.rollback(require_root=True)
class SnapshotRollbackTask(Task):
    """Rollback vers un snapshot."""

    def required_locks(self):
        ds = self.params.get("dataset", "")
        return [Lock(f"dataset.{ds.replace('/', '.')}", owner_id=str(self.id), exclusive=True)]

    def validate(self) -> bool:
        return self.params.get("confirmed", False)

    def run(self) -> dict[str, Any]:
        snapshot = self.params.get("snapshot", "")
        force = self.params.get("force", False)
        destroy_recent = self.params.get("destroy_recent", False)

        if not snapshot:
            raise ValueError("snapshot required (dataset@name)")

        cmd_parts = ["zfs", "rollback"]
        if force:
            cmd_parts.append("-f")
        if destroy_recent:
            cmd_parts.append("-r")
        cmd_parts.append(snapshot)

        self.run_cmd(cmd_parts, sudo=True)
        return {"snapshot": snapshot, "rolled_back": True}


@security.dataset.snapshot.send
class SnapshotSendTask(Task):
    """Envoie un snapshot (zfs send | zfs recv)."""

    executor = "threaded"

    def required_locks(self):
        src = self.params.get("source", "")
        ds = src.split("@")[0] if "@" in src else src
        return [Lock(f"dataset.{ds.replace('/', '.')}.send", owner_id=str(self.id))]

    def run(self) -> dict[str, Any]:
        source = self.params.get("source", "")
        target = self.params.get("target", "")
        incremental = self.params.get("incremental", "")
        compress = self.params.get("compress", "zstd")
        raw = self.params.get("raw", True)

        if not source:
            raise ValueError("source snapshot required")

        send_parts = ["zfs", "send", "-p"]
        if raw:
            send_parts.append("-w")
        if incremental:
            send_parts.extend(["-i", incremental])
        send_parts.append(source)

        if target:
            # Local receive
            recv_parts = ["zfs", "recv", "-u", "-o", "canmount=noauto",
                         "-o", "mountpoint=/", target]
            cmd = f"{' '.join(send_parts)} | pv | {' '.join(recv_parts)}"
        else:
            # Export to file
            output = self.params.get("output", f"/tmp/{source.replace('/', '_').replace('@', '_')}.zfs")
            compress_cmd = {"zstd": "zstd -T0", "xz": "xz -T0", "gzip": "gzip", "lz4": "lz4"}.get(compress, "cat")
            cmd = f"{' '.join(send_parts)} | {compress_cmd} > {output}"

        self.run_cmd(f"bash -c '{cmd}'", sudo=True, timeout=3600)

        return {"source": source, "target": target or output, "sent": True}


@security.dataset.snapshot.list
class SnapshotListTask(Task):
    """Liste les snapshots."""

    def run(self) -> list[dict[str, str]]:
        dataset = self.params.get("dataset", "")
        properties = ["name", "used", "creation"]

        cmd = f"zfs list -t snapshot -H -o {','.join(properties)}"
        if dataset:
            cmd += f" -r {dataset}"

        result = self.run_cmd(cmd, check=False)
        if not result.success:
            return []

        snapshots = []
        for line in result.stdout.strip().splitlines():
            parts = line.split("\t")
            if len(parts) >= len(properties):
                snapshots.append(dict(zip(properties, parts)))
        return snapshots
