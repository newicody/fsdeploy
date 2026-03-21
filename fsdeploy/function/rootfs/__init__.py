"""fsdeploy.function.rootfs — Gestion du rootfs overlay."""
from function.rootfs.switch import (
    RootfsMountTask,
    RootfsSwitchTask,
    RootfsUpdateTask,
    RootfsUmountTask,
)

__all__ = [
    "RootfsMountTask",
    "RootfsSwitchTask",
    "RootfsUpdateTask",
    "RootfsUmountTask",
]
