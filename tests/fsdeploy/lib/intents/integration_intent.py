"""
Intent pour lancer les tests d'intégration.
"""
from fsdeploy.lib.scheduler.model.intent import Intent
from fsdeploy.lib.scheduler.core.registry import register_intent

@register_intent("integration.test")
class IntegrationTestIntent(Intent):
    """Intent pour exécuter les tests d'intégration."""

    def build_tasks(self):
        from fsdeploy.lib.function.integration_test import IntegrationTestTask
        return [IntegrationTestTask(
            id=f"integration_test_{self.params.get('distro','all')}",
            params=self.params,
            context=self.context,
        )]
