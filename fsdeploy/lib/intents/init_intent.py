"""
Intention de détection du système d'initialisation.
"""

from fsdeploy.lib.scheduler.model.intent import Intent
from fsdeploy.lib.scheduler.core.registry import register_intent
from fsdeploy.lib.function.init.check import InitCheckTask
from fsdeploy.lib.function.init.install import InstallInitIntegrationTask
from fsdeploy.lib.function.init.boot_check import BootIntegrationCheckTask
from fsdeploy.lib.function.init_install import InitInstallTask, InitConfigureTask

@register_intent("init.detect")
class InitDetectIntent(Intent):
    def build_tasks(self):
        return [
            InitCheckTask(
                id="init_detect",
                params=self.params,
                context=self.context
            )
        ]

@register_intent("init.service.control")
class InitServiceControlIntent(Intent):
    """
    Intent pour contrôler (start/stop/restart) le service fsdeploy.
    """
    def build_tasks(self):
        from fsdeploy.lib.function.init_install import InitServiceControlTask
        return [
            InitServiceControlTask(
                id="init_service_control",
                params=self.params,
                context=self.context,
            )
        ]

@register_intent("init.integration.install")
class InitIntegrationInstallIntent(Intent):
    def build_tasks(self):
        return [
            InstallInitIntegrationTask(
                id="init_integration_install",
                params=self.params,
                context=self.context
            )
        ]

@register_intent("init.boot.check")
class InitBootCheckIntent(Intent):
    def build_tasks(self):
        return [
            BootIntegrationCheckTask(
                id="init_boot_check",
                params=self.params,
                context=self.context
            )
        ]

@register_intent("init.install")
class InitInstallIntent(Intent):
    """
    Intent pour installer les scripts d'intégration du système d'initialisation détecté.
    """
    def build_tasks(self):
        return [
            InitInstallTask(
                id="init_install",
                params=self.params,
                context=self.context,
            )
        ]

@register_intent("init.configure")
class InitConfigureIntent(Intent):
    """
    Intent pour configurer finement le système d'initialisation.
    """
    def build_tasks(self):
        return [
            InitConfigureTask(
                id="init_configure",
                params=self.params,
                context=self.context,
            )
        ]

@register_intent("init.config.detect")
class InitConfigDetectIntent(Intent):
    """
    Intent pour détecter le système d'initialisation cible et live.
    """
    def build_tasks(self):
        from fsdeploy.lib.function.init_install import InitConfigDetectTask
        return [
            InitConfigDetectTask(
                id="init_config_detect",
                params=self.params,
                context=self.context,
            )
        ]

@register_intent("init.postinstall.check")
class InitPostInstallCheckIntent(Intent):
    """
    Intent pour vérifier l'installation du service fsdeploy.
    """
    def build_tasks(self):
        from fsdeploy.lib.function.init_install import InitPostInstallCheckTask
        return [
            InitPostInstallCheckTask(
                id="init_postinstall_check",
                params=self.params,
                context=self.context,
            )
        ]
