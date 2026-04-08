"""
Intent pour la détection et l'intégration des modules du noyau Linux.
"""
from fsdeploy.lib.scheduler.model.intent import Intent
from fsdeploy.lib.scheduler.core.registry import register_intent

@register_intent("kernel.module.detect")
class KernelModuleDetectIntent(Intent):
    """Intent pour détecter les modules du noyau (squashfs, partitions)."""

    def build_tasks(self):
        from fsdeploy.lib.function.kernel_module_detect import KernelModuleDetectTask
        return [KernelModuleDetectTask(
            id="kernel_module_detect",
            params=self.params,
            context=self.context,
        )]

@register_intent("kernel.module.integrate")
class KernelModuleIntegrateIntent(Intent):
    """Intent pour intégrer les modules détectés dans l'initramfs."""

    def build_tasks(self):
        from fsdeploy.lib.function.kernel_module_integrate import KernelModuleIntegrateTask
        return [KernelModuleIntegrateTask(
            id="kernel_module_integrate",
            params=self.params,
            context=self.context,
        )]
