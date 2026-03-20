"""
fsdeploy.function.pool.status
==============================
Opérations sur les pools ZFS : import, export, status, scrub.
"""

from pathlib import Path
from typing import Any

from scheduler.model.task import Task
from scheduler.model.resource import Resource, pool_resource
from scheduler.model.lock import Lock
from scheduler.security.decorator import security


@security.pool.status
class PoolStatusTask(Task):
    """Affiche le statut complet d'un pool."""

    def run(self) -> dict[str, Any]:
        pool = self.params.get("pool", "")
        cmd = f"zpool status -v {pool}" if pool else "zpool status -v"
        result = self.run_cmd(cmd, check=False)
        return {
            "pool": pool or "all",
            "output": result.stdout,
            "healthy": "ONLINE" in result.stdout and "DEGRADED" not in result.stdout,
        }


@security.pool.import_pool(require_root=True)
class PoolImportTask(Task):
    """Importe un pool ZFS."""

    def required_locks(self):
        pool = self.params.get("pool", "")
        return [Lock(f"pool.{pool}", owner_id=str(self.id))] if pool else []

    def run(self) -> dict[str, Any]:
        pool = self.params.get("pool", "")
        force = self.params.get("force", False)
        readonly = self.params.get("readonly", False)
        no_mount = self.params.get("no_mount", True)

        if not pool:
            # Lister les pools importables
            r = self.run_cmd("zpool import", sudo=True, check=False)
            return {"action": "list", "output": r.stdout}

        cmd_parts = ["zpool", "import"]
        if force:
            cmd_parts.append("-f")
        if no_mount:
            cmd_parts.append("-N")
        if readonly:
            cmd_parts.extend(["-o", "readonly=on"])
        cmd_parts.extend(["-o", "cachefile=none"])
        cmd_parts.append(pool)

        self.run_cmd(cmd_parts, sudo=True)
        return {"pool": pool, "imported": True}


@security.pool.export_pool(require_root=True)
class PoolExportTask(Task):
    """Exporte un pool ZFS."""

    def required_locks(self):
        pool = self.params.get("pool", "")
        return [Lock(f"pool.{pool}", owner_id=str(self.id), exclusive=True)] if pool else []

    def run(self) -> dict[str, Any]:
        pool = self.params.get("pool", "")
        force = self.params.get("force", False)

        if not pool:
            raise ValueError("pool name required")

        cmd_parts = ["zpool", "export"]
        if force:
            cmd_parts.append("-f")
        cmd_parts.append(pool)

        self.run_cmd(cmd_parts, sudo=True)
        return {"pool": pool, "exported": True}


@security.pool.scrub(require_root=True)
class PoolScrubTask(Task):
    """Lance un scrub sur un pool."""

    executor = "threaded"

    def required_locks(self):
        pool = self.params.get("pool", "")
        return [Lock(f"pool.{pool}.scrub", owner_id=str(self.id))] if pool else []

    def run(self) -> dict[str, Any]:
        pool = self.params.get("pool", "")
        stop = self.params.get("stop", False)

        if not pool:
            raise ValueError("pool name required")

        if stop:
            self.run_cmd(f"zpool scrub -s {pool}", sudo=True, check=False)
            return {"pool": pool, "action": "stopped"}

        self.run_cmd(f"zpool scrub {pool}", sudo=True)
        return {"pool": pool, "action": "started"}
