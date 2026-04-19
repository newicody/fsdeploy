# -*- coding: utf-8 -*-
"""
Intents pour le montage SquashFS et la gestion overlay.
"""

from fsdeploy.lib.scheduler.model.intent import Intent
from fsdeploy.lib.scheduler.core.registry import register_intent


@register_intent("overlay.squashfs.mount")
class SquashfsMountIntent(Intent):
    def build_tasks(self):
        from fsdeploy.lib.function.rootfs.overlay import SquashfsMountTask
        return [SquashfsMountTask(
            id="squashfs_mount", params=self.params, context=self.context)]


@register_intent("overlay.setup")
class OverlaySetupIntent(Intent):
    def build_tasks(self):
        from fsdeploy.lib.function.rootfs.overlay import OverlaySetupTask
        return [OverlaySetupTask(
            id="overlay_setup", params=self.params, context=self.context)]


@register_intent("overlay.teardown")
class OverlayTeardownIntent(Intent):
    def build_tasks(self):
        from fsdeploy.lib.function.rootfs.overlay import OverlayTeardownTask
        return [OverlayTeardownTask(
            id="overlay_teardown", params=self.params, context=self.context)]


@register_intent("overlay.mount")
class OverlayFullMountIntent(Intent):
    """
    Mount complet : squashfs + overlay en une seule operation.
    Cree 2 tasks en sequence.
    """
    def build_tasks(self):
        from fsdeploy.lib.function.rootfs.overlay import (
            SquashfsMountTask, OverlaySetupTask,
        )
        sfs_path = self.params.get("squashfs_path", "")
        merged = self.params.get("merged", "")
        lower = self.params.get("lower", f"/mnt/squashfs-lower")

        return [
            SquashfsMountTask(
                id="squashfs_mount",
                params={"squashfs_path": sfs_path, "mountpoint": lower},
                context=self.context,
            ),
            OverlaySetupTask(
                id="overlay_setup",
                params={**self.params, "lower": lower, "merged": merged},
                context=self.context,
            ),
        ]
