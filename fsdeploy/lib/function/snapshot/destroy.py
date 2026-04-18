"""
Destruction d'un snapshot ZFS.
"""
from typing import Any
from fsdeploy.lib.scheduler.model.task import Task
from fsdeploy.lib.scheduler.model.lock import Lock


class SnapshotDestroyTask(Task):
    """Detruit un snapshot ZFS."""

    def required_locks(self):
        ds = self.params.get("dataset", "")
        return [Lock(f"dataset.{ds.replace('/', '.')}", owner_id=str(self.id), exclusive=True)]

    def validate(self) -> bool:
        return self.params.get("confirmed", False)

    def run(self) -> dict[str, Any]:
        snapshot = self.params.get("snapshot", "")
        if not snapshot:
            raise ValueError("snapshot required (dataset@name)")
        cmd = f"zfs destroy {snapshot}"
        result = self._run_cmd(cmd)
        return {"snapshot": snapshot, "destroyed": result.get("success", False)}
