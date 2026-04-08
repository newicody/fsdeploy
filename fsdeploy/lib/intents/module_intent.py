"""
Intents pour la gestion des modules tiers (désactivées).
Le système de modules dynamiques a été jugé non nécessaire pour le moment.
"""
from fsdeploy.lib.scheduler.model.intent import Intent, register_intent

# Les intents sont désactivées et ne font rien.
@register_intent("module.list")
class ModuleListIntent(Intent):
    def build_tasks(self):
        return []

@register_intent("module.install")
class ModuleInstallIntent(Intent):
    def build_tasks(self):
        return []

@register_intent("module.uninstall")
class ModuleUninstallIntent(Intent):
    def build_tasks(self):
        return []

@register_intent("module.update")
class ModuleUpdateIntent(Intent):
    def build_tasks(self):
        return []
