"""
Intent pour l'intégration avec ZFSBootMenu.
"""
from fsdeploy.lib.scheduler.model.intent import Intent
from fsdeploy.lib.scheduler.core.registry import register_intent


@register_intent("zfsbootmenu.integrate")
class ZFSBootMenuIntegrateIntent(Intent):
    """Intent pour détecter et configurer ZFSBootMenu."""

    def build_tasks(self):
        from fsdeploy.lib.function.zfsbootmenu_integrate import ZFSBootMenuIntegrateTask
        return [ZFSBootMenuIntegrateTask(
            id="zfsbootmenu_integrate",
            params=self.params,
            context=self.context,
        )]
