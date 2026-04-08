"""
Intent pour l'installation des scripts upstart et sysvinit.
"""
from fsdeploy.lib.scheduler.model.intent import Intent
from fsdeploy.lib.scheduler.core.registry import register_intent


@register_intent("init.upstart_sysv.install")
class UpstartSysvInstallIntent(Intent):
    """Intent pour installer les scripts upstart et sysvinit."""

    def build_tasks(self):
        from fsdeploy.lib.function.init_upstart_sysv import UpstartSysvInstallTask
        return [UpstartSysvInstallTask(
            id="upstart_sysv_install",
            params=self.params,
            context=self.context,
        )]


@register_intent("init.upstart_sysv.test")
class UpstartSysvTestIntent(Intent):
    """Intent pour tester l'installation des scripts upstart et sysvinit."""

    def build_tasks(self):
        from fsdeploy.lib.function.init_upstart_sysv import UpstartSysvTestTask
        return [UpstartSysvTestTask(
            id="upstart_sysv_test",
            params=self.params,
            context=self.context,
        )]
