"""
Tâches pour le registre de modules tiers.
"""

from fsdeploy.lib.scheduler.model.task import Task
from fsdeploy.lib.scheduler.model.intent import Intent
from fsdeploy.lib.scheduler.core.registry import register_intent

class ModuleRegistryInstallTask(Task):
    """Installe un module tiers."""

    def run(self):
        name = self.context.get("name", "")
        version = self.context.get("version", "")
        # Simulation
        return {
            "success": True,
            "module": {"name": name, "version": version or "1.0.0", "status": "installed"}
        }

class ModuleRegistryUpdateTask(Task):
    """Met à jour un module tiers."""

    def run(self):
        name = self.context.get("name", "")
        # Simulation
        return {"success": True, "message": f"Module {name} mis à jour."}

class ModuleRegistryDeleteTask(Task):
    """Supprime un module tiers."""

    def run(self):
        name = self.context.get("name", "")
        # Simulation
        return {"success": True, "message": f"Module {name} supprimé."}

@register_intent("moduleregistry.install")
class ModuleRegistryInstallIntent(Intent):
    def build_tasks(self):
        return [ModuleRegistryInstallTask()]

@register_intent("moduleregistry.update")
class ModuleRegistryUpdateIntent(Intent):
    def build_tasks(self):
        return [ModuleRegistryUpdateTask()]

@register_intent("moduleregistry.delete")
class ModuleRegistryDeleteIntent(Intent):
    def build_tasks(self):
        return [ModuleRegistryDeleteTask()]
