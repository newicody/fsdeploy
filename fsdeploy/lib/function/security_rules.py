"""
Tâches pour gérer les règles de sécurité.
"""

from fsdeploy.lib.scheduler.model.task import Task
from fsdeploy.lib.scheduler.model.intent import Intent
from fsdeploy.lib.scheduler.core.registry import register_intent

class SecurityRulesViewTask(Task):
    """Récupère la liste des règles de sécurité."""

    def run(self):
        # Récupérer depuis la configuration de sécurité
        # Pour l'instant simulé
        rules = [
            {"path": "pool.*", "action": "allow", "source": "config"},
            {"path": "dataset.*.home", "action": "deny", "source": "default"},
        ]
        return {"rules": rules}


class SecurityRulesModifyTask(Task):
    """Modifie une règle de sécurité."""

    def run(self):
        # paramètres dans self.context
        path = self.context.get("path")
        action = self.context.get("action")
        # Appliquer la modification
        return {"success": True, "message": f"Règle {path} -> {action}"}


class SecurityRulesDeleteTask(Task):
    """Supprime une règle de sécurité."""

    def run(self):
        path = self.context.get("path")
        # Simuler la suppression
        return {"success": True, "message": f"Règle {path} supprimée"}


@register_intent("security.rules.view")
class SecurityRulesViewIntent(Intent):
    def build_tasks(self):
        return [SecurityRulesViewTask()]


@register_intent("security.rules.modify")
class SecurityRulesModifyIntent(Intent):
    def build_tasks(self):
        return [SecurityRulesModifyTask()]


@register_intent("security.rules.delete")
class SecurityRulesDeleteIntent(Intent):
    def build_tasks(self):
        return [SecurityRulesDeleteTask()]
