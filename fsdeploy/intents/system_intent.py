"""
fsdeploy.intents.system_intent
================================
Intents système : cohérence, snapshots, stream, réseau, rootfs.

Events supportés :
  coherence.check
  snapshot.list, snapshot.create, snapshot.rollback, snapshot.send
  stream.start, stream.stop, stream.status, stream.test, stream.restart
  network.setup, network.status, network.wait
  rootfs.mount, rootfs.switch, rootfs.update, rootfs.umount
  service.install, service.uninstall, service.status
"""

from scheduler.model.intent import Intent
from scheduler.core.registry import register_intent


# ═══════════════════════════════════════════════════════════════════
# COHERENCE
# ═══════════════════════════════════════════════════════════════════

@register_intent("coherence.check")
class CoherenceCheckIntent(Intent):
    """Vérifie la cohérence complète du système."""

    def build_tasks(self):
        from function.coherence.check import CoherenceCheckTask
        return [CoherenceCheckTask(
            id="coherence_check",
            params=self.params,
            context=self.context,
        )]


# ═══════════════════════════════════════════════════════════════════
# SNAPSHOTS
# ═══════════════════════════════════════════════════════════════════

@register_intent("snapshot.list")
class SnapshotListIntent(Intent):
    def build_tasks(self):
        from function.snapshot.create import SnapshotListTask
        return [SnapshotListTask(
            id="snap_list",
            params=self.params,
            context=self.context,
        )]


@register_intent("snapshot.create")
class SnapshotCreateIntent(Intent):
    def build_tasks(self):
        from function.snapshot.create import SnapshotCreateTask
        return [SnapshotCreateTask(
            id="snap_create",
            params=self.params,
            context=self.context,
        )]


@register_intent("snapshot.rollback")
class SnapshotRollbackIntent(Intent):
    def build_tasks(self):
        from function.snapshot.create import SnapshotRollbackTask
        return [SnapshotRollbackTask(
            id="snap_rollback",
            params=self.params,
            context=self.context,
        )]


@register_intent("snapshot.send")
class SnapshotSendIntent(Intent):
    def build_tasks(self):
        from function.snapshot.create import SnapshotSendTask
        return [SnapshotSendTask(
            id="snap_send",
            params=self.params,
            context=self.context,
        )]


# ═══════════════════════════════════════════════════════════════════
# STREAM
# ═══════════════════════════════════════════════════════════════════

@register_intent("stream.start")
class StreamStartIntent(Intent):
    def build_tasks(self):
        from function.stream.youtube import StreamStartTask
        return [StreamStartTask(
            id="stream_start",
            params=self.params,
            context=self.context,
        )]


@register_intent("stream.stop")
class StreamStopIntent(Intent):
    def build_tasks(self):
        from function.stream.youtube import StreamStopTask
        return [StreamStopTask(
            id="stream_stop",
            params=self.params,
            context=self.context,
        )]


@register_intent("stream.status")
class StreamStatusIntent(Intent):
    def build_tasks(self):
        from function.stream.youtube import StreamStatusTask
        return [StreamStatusTask(
            id="stream_status",
            params=self.params,
            context=self.context,
        )]


@register_intent("stream.test")
class StreamTestIntent(Intent):
    def build_tasks(self):
        from function.stream.youtube import StreamTestTask
        return [StreamTestTask(
            id="stream_test",
            params=self.params,
            context=self.context,
        )]


@register_intent("stream.restart")
class StreamRestartIntent(Intent):
    def build_tasks(self):
        from function.stream.youtube import StreamRestartTask
        return [StreamRestartTask(
            id="stream_restart",
            params=self.params,
            context=self.context,
        )]


# ═══════════════════════════════════════════════════════════════════
# NETWORK
# ═══════════════════════════════════════════════════════════════════

@register_intent("network.setup")
class NetworkSetupIntent(Intent):
    def build_tasks(self):
        from function.network.setup import NetworkSetupTask
        return [NetworkSetupTask(
            id="network_setup",
            params=self.params,
            context=self.context,
        )]


@register_intent("network.status")
class NetworkStatusIntent(Intent):
    def build_tasks(self):
        from function.network.setup import NetworkStatusTask
        return [NetworkStatusTask(
            id="network_status",
            params=self.params,
            context=self.context,
        )]


@register_intent("network.wait")
class NetworkWaitIntent(Intent):
    def build_tasks(self):
        from function.network.setup import NetworkWaitTask
        return [NetworkWaitTask(
            id="network_wait",
            params=self.params,
            context=self.context,
        )]


# ═══════════════════════════════════════════════════════════════════
# ROOTFS
# ═══════════════════════════════════════════════════════════════════

@register_intent("rootfs.mount")
class RootfsMountIntent(Intent):
    def build_tasks(self):
        from function.rootfs.switch import RootfsMountTask
        return [RootfsMountTask(
            id="rootfs_mount",
            params=self.params,
            context=self.context,
        )]


@register_intent("rootfs.switch")
class RootfsSwitchIntent(Intent):
    def build_tasks(self):
        from function.rootfs.switch import RootfsSwitchTask
        return [RootfsSwitchTask(
            id="rootfs_switch",
            params=self.params,
            context=self.context,
        )]


@register_intent("rootfs.update")
class RootfsUpdateIntent(Intent):
    def build_tasks(self):
        from function.rootfs.switch import RootfsUpdateTask
        return [RootfsUpdateTask(
            id="rootfs_update",
            params=self.params,
            context=self.context,
        )]


@register_intent("rootfs.umount")
class RootfsUmountIntent(Intent):
    def build_tasks(self):
        from function.rootfs.switch import RootfsUmountTask
        return [RootfsUmountTask(
            id="rootfs_umount",
            params=self.params,
            context=self.context,
        )]


# ═══════════════════════════════════════════════════════════════════
# SERVICE
# ═══════════════════════════════════════════════════════════════════

@register_intent("service.install")
class ServiceInstallIntent(Intent):
    def build_tasks(self):
        from function.service.install import ServiceInstallTask
        return [ServiceInstallTask(
            id="service_install",
            params=self.params,
            context=self.context,
        )]


@register_intent("service.uninstall")
class ServiceUninstallIntent(Intent):
    def build_tasks(self):
        from function.service.install import ServiceUninstallTask
        return [ServiceUninstallTask(
            id="service_uninstall",
            params=self.params,
            context=self.context,
        )]


@register_intent("service.status")
class ServiceStatusIntent(Intent):
    def build_tasks(self):
        from function.service.install import ServiceStatusTask
        return [ServiceStatusTask(
            id="service_status",
            params=self.params,
            context=self.context,
        )]
