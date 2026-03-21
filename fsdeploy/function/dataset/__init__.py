"""fsdeploy.function.dataset — Opérations sur les datasets ZFS."""
from function.dataset.mount import (
    DatasetMountTask,
    DatasetCreateTask,
    DatasetDestroyTask,
    DatasetListTask,
)

__all__ = [
    "DatasetMountTask",
    "DatasetCreateTask",
    "DatasetDestroyTask",
    "DatasetListTask",
]
