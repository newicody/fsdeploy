"""
Intent pour la configuration fine des paramètres de boot.
"""
from fsdeploy.lib.scheduler.model.intent import Intent
from fsdeploy.lib.scheduler.core.registry import register_intent


@register_intent("init.boot.config")
class InitBootConfigIntent(Intent):
    """Intent pour configurer les paramètres de boot."""

    def build_tasks(self):
        from fsdeploy.lib.function.init_boot_config import InitBootConfigTask
        return [InitBootConfigTask(
            id="init_boot_config",
            params=self.params,
            context=self.context,
        )]
