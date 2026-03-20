"""
fsdeploy.intents.boot_intent
==============================
Intent de boot : orchestre la séquence complète pour démarrer un preset.

Séquence :
  1. Détection environnement
  2. Import pools
  3. Mount datasets
  4. Sélection kernel
  5. Vérification cohérence
  6. Construction initramfs (si nécessaire)
  7. Installation ZBM (si nécessaire)
"""

from typing import Any

from scheduler.model.intent import Intent
from scheduler.core.registry import register_intent

from function.detect.environment import EnvironmentDetectTask
from function.pool.status import PoolImportTask
from function.dataset.mount import DatasetMountTask
from function.kernel.switch import KernelSwitchTask
from function.coherence.check import CoherenceCheckTask
from function.boot.initramfs import InitramfsBuildTask


@register_intent("boot.request")
class BootIntent(Intent):
    """
    Intent principal : prépare et vérifie le boot.
    """

    def build_tasks(self) -> list:
        preset = self.params.get("preset", {})
        tasks = []

        # 1. Détection environnement
        tasks.append(EnvironmentDetectTask(
            id="env_detect",
            params={},
            context=self.context,
        ))

        # 2. Import pools
        pools = preset.get("pools", [])
        for pool_name in pools:
            tasks.append(PoolImportTask(
                id=f"import_{pool_name}",
                params={"pool": pool_name, "no_mount": True},
                context=self.context,
            ))

        # 3. Mount datasets
        datasets = preset.get("datasets", [])
        for ds_config in datasets:
            tasks.append(DatasetMountTask(
                id=f"mount_{ds_config['dataset'].replace('/', '_')}",
                params=ds_config,
                context=self.context,
            ))

        # 4. Kernel switch
        kernel_version = preset.get("kernel_version", "")
        if kernel_version:
            tasks.append(KernelSwitchTask(
                id="kernel_switch",
                params={
                    "version": kernel_version,
                    "boot_path": preset.get("boot_path", "/boot"),
                },
                context=self.context,
            ))

        # 5. Initramfs (si rebuild demandé)
        if preset.get("rebuild_initramfs", False):
            tasks.append(InitramfsBuildTask(
                id="initramfs_build",
                params={
                    "kernel_version": kernel_version,
                    "init_type": preset.get("init_type", "zbm"),
                    "method": preset.get("initramfs_method", "dracut"),
                    "compress": preset.get("compress", "zstd"),
                    "force": True,
                },
                context=self.context,
            ))

        # 6. Coherence check
        tasks.append(CoherenceCheckTask(
            id="coherence_check",
            params={"preset": preset},
            context=self.context,
        ))

        return tasks


@register_intent("cli.snapshot")
class SnapshotIntent(Intent):
    """Intent pour créer un snapshot depuis la CLI ou le timer."""

    def build_tasks(self) -> list:
        from function.snapshot.create import SnapshotCreateTask
        return [SnapshotCreateTask(
            id="snapshot",
            params=self.params,
            context=self.context,
        )]


@register_intent("cli.stream_start")
class StreamStartIntent(Intent):
    """Intent pour démarrer le stream YouTube."""

    def build_tasks(self) -> list:
        from function.network.setup import NetworkSetupTask
        from function.stream.youtube import StreamStartTask
        tasks = []

        # D'abord le réseau
        tasks.append(NetworkSetupTask(
            id="network_setup",
            params={"timeout": self.params.get("network_timeout", 30)},
            context=self.context,
        ))

        # Puis le stream
        tasks.append(StreamStartTask(
            id="stream_start",
            params=self.params,
            context=self.context,
        ))

        return tasks


@register_intent("timer.coherence_check")
class PeriodicCoherenceIntent(Intent):
    """Vérification périodique de cohérence."""

    def build_tasks(self) -> list:
        return [CoherenceCheckTask(
            id="periodic_coherence",
            params=self.params,
            context=self.context,
        )]


@register_intent("timer.snapshot_auto")
class AutoSnapshotIntent(Intent):
    """Snapshots automatiques périodiques."""

    def build_tasks(self) -> list:
        from function.snapshot.create import SnapshotCreateTask
        datasets = self.params.get("datasets", [])
        tasks = []
        for ds in datasets:
            tasks.append(SnapshotCreateTask(
                id=f"auto_snap_{ds.replace('/', '_')}",
                params={"dataset": ds, "name": ""},  # nom auto-généré
                context=self.context,
            ))
        return tasks


@register_intent("timer.scrub_check")
class ScrubIntent(Intent):
    """Lance un scrub sur les pools configurés."""

    def build_tasks(self) -> list:
        from function.pool.status import PoolScrubTask
        pools = self.params.get("pools", [])
        return [
            PoolScrubTask(
                id=f"scrub_{pool}",
                params={"pool": pool},
                context=self.context,
            )
            for pool in pools
        ]
