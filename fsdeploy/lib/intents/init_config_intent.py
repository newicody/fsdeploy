"""
Intent pour la configuration et détection des systèmes d'init.
"""
from fsdeploy.lib.scheduler.model.intent import Intent
from fsdeploy.lib.scheduler.core.registry import register_intent

@register_intent("init.config.detect")
class InitConfigDetectIntent(Intent):
    """Intent pour détecter la configuration d'init sur cible et live."""

    def build_tasks(self):
        from fsdeploy.lib.function.init_config import InitConfigDetectTask
        return [InitConfigDetectTask(
            id="init_config_detect",
            params=self.params,
            context=self.context,
        )]
