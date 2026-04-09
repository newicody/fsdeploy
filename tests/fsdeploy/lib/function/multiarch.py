"""
Tâches pour la gestion multi‑architectures.
"""

from fsdeploy.lib.scheduler.model.task import Task
from fsdeploy.lib.scheduler.model.intent import Intent
from fsdeploy.lib.scheduler.core.registry import register_intent

class MultiArchSyncTask(Task):
    """Synchronise les noyaux et initramfs pour une architecture."""

    def run(self):
        arch = self.context.get("arch", "aarch64")
        registry = self.context.get("registry", "")
        # Simulation
        kernels = [
            {"arch": arch, "version": "6.6.47", "path": f"/boot/vmlinuz-{arch}"},
            {"arch": arch, "version": "6.12.0", "path": f"/boot/vmlinuz-{arch}-edge"},
        ]
        return {"success": True, "kernels": kernels}

class MultiArchListTask(Task):
    """Liste les noyaux disponibles pour une architecture."""

    def run(self):
        arch = self.context.get("arch", "aarch64")
        # Simulation
        kernels = [
            {"arch": arch, "version": "6.6.47", "path": f"/boot/vmlinuz-{arch}"},
            {"arch": arch, "version": "6.12.0", "path": f"/boot/vmlinuz-{arch}-edge"},
        ]
        return {"success": True, "kernels": kernels}

@register_intent("multiarch.sync")
class MultiArchSyncIntent(Intent):
    def build_tasks(self):
        return [MultiArchSyncTask()]

@register_intent("multiarch.list")
class MultiArchListIntent(Intent):
    def build_tasks(self):
        return [MultiArchListTask()]
