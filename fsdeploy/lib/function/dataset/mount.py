"""
fsdeploy.function.dataset.mount
================================
Opérations sur les datasets ZFS : mount, create, destroy, list.

Principe : détection par contenu, pas par nom codé en dur.
"""

import json
from pathlib import Path
from typing import Any

from scheduler.model.task import Task
from scheduler.model.resource import Resource, dataset_resource
from scheduler.model.lock import Lock
from scheduler.security.decorator import security


@security.dataset.mount
class DatasetMountTask(Task):
    """Monte un dataset ZFS."""

    def required_locks(self):
        ds = self.params.get("dataset", "")
        if ds:
            return [Lock(f"dataset.{ds.replace('/', '.')}", owner_id=str(self.id))]
        return []

    def run(self) -> dict[str, Any]:
        dataset = self.params.get("dataset", "")
        mountpoint = self.params.get("mountpoint", "")

        if not dataset:
            raise ValueError("dataset name required")

        # Vérifier si déjà monté
        r = self.run_cmd(f"zfs get -H -o value mounted {dataset}", check=False)
        if r.success and r.stdout.strip() == "yes":
            # Trouver le mountpoint actuel
            r2 = self.run_cmd(f"zfs get -H -o value mountpoint {dataset}", check=False)
            current_mp = r2.stdout.strip() if r2.success else ""
            return {"dataset": dataset, "mountpoint": current_mp, "already_mounted": True}

        # Vérifier le type de mountpoint (legacy vs normal)
        r = self.run_cmd(f"zfs get -H -o value mountpoint {dataset}", check=False)
        mp_value = r.stdout.strip() if r.success else ""

        if mp_value in ("legacy", "none") or mountpoint:
            # mount -t zfs (canonical form pour legacy)
            if not mountpoint:
                mountpoint = f"/mnt/{dataset.replace('/', '_')}"
            Path(mountpoint).mkdir(parents=True, exist_ok=True)
            self.run_cmd(
                f"mount -t zfs {dataset} {mountpoint}",
                sudo=True,
            )
        else:
            # zfs mount standard
            self.run_cmd(f"zfs mount {dataset}", sudo=True)
            mountpoint = mp_value

        return {"dataset": dataset, "mountpoint": mountpoint, "mounted": True}


@security.dataset.create(require_root=True)
class DatasetCreateTask(Task):
    """Crée un dataset ZFS."""

    def required_locks(self):
        ds = self.params.get("dataset", "")
        pool = ds.split("/")[0] if "/" in ds else ds
        return [Lock(f"pool.{pool}", owner_id=str(self.id))]

    def run(self) -> dict[str, Any]:
        dataset = self.params.get("dataset", "")
        properties = self.params.get("properties", {})
        parents = self.params.get("parents", True)

        if not dataset:
            raise ValueError("dataset name required")

        cmd_parts = ["zfs", "create"]
        if parents:
            cmd_parts.append("-p")

        for key, val in properties.items():
            cmd_parts.extend(["-o", f"{key}={val}"])

        cmd_parts.append(dataset)
        self.run_cmd(cmd_parts, sudo=True)

        return {"dataset": dataset, "created": True, "properties": properties}


@security.dataset.destroy(require_root=True)
class DatasetDestroyTask(Task):
    """Détruit un dataset ZFS (avec confirmation obligatoire)."""

    def required_locks(self):
        ds = self.params.get("dataset", "")
        return [Lock(f"dataset.{ds.replace('/', '.')}", owner_id=str(self.id), exclusive=True)]

    def validate(self) -> bool:
        """La destruction requiert une confirmation explicite."""
        return self.params.get("confirmed", False)

    def run(self) -> dict[str, Any]:
        dataset = self.params.get("dataset", "")
        recursive = self.params.get("recursive", False)
        force = self.params.get("force", False)

        if not dataset:
            raise ValueError("dataset name required")

        cmd_parts = ["zfs", "destroy"]
        if recursive:
            cmd_parts.append("-r")
        if force:
            cmd_parts.append("-f")
        cmd_parts.append(dataset)

        self.run_cmd(cmd_parts, sudo=True)
        return {"dataset": dataset, "destroyed": True}


@security.dataset.list
class DatasetListTask(Task):
    """Liste les datasets d'un pool avec leurs propriétés."""

    def run(self) -> list[dict[str, str]]:
        pool = self.params.get("pool", "")
        properties = self.params.get("properties", [
            "name", "used", "avail", "mountpoint", "mounted", "creation",
        ])

        cmd = f"zfs list -H -o {','.join(properties)}"
        if pool:
            cmd += f" -r {pool}"

        result = self.run_cmd(cmd, check=False)
        if not result.success:
            return []

        datasets = []
        for line in result.stdout.strip().splitlines():
            parts = line.split("\t")
            if len(parts) >= len(properties):
                datasets.append(dict(zip(properties, parts)))

        return datasets
