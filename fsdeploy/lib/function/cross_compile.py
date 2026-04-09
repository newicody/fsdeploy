"""
Tâches pour la compilation croisée.
"""

from fsdeploy.lib.scheduler.model.task import Task
from fsdeploy.lib.scheduler.model.intent import Intent
from fsdeploy.lib.scheduler.core.registry import register_intent

class CrossCompileLaunchTask(Task):
    """Lance une compilation croisée."""

    def run(self):
        arch = self.context.get("arch", "aarch64")
        kernel = self.context.get("kernel", "")
        # Simulation
        return {"success": True, "message": f"Compilation {arch} pour kernel {kernel} lancée."}

class CrossCompileStopTask(Task):
    """Arrête une compilation en cours."""

    def run(self):
        # Simulation
        return {"success": True, "message": "Compilation arrêtée."}

@register_intent("crosscompile.launch")
class CrossCompileLaunchIntent(Intent):
    def build_tasks(self):
        return [CrossCompileLaunchTask()]

@register_intent("crosscompile.stop")
class CrossCompileStopIntent(Intent):
    def build_tasks(self):
        return [CrossCompileStopTask()]
