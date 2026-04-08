"""
Intent pour la détection des noyaux mainline et des modules externes.
"""
from fsdeploy.lib.scheduler.model.intent import Intent
from fsdeploy.lib.scheduler.core.registry import register_intent


@register_intent("kernel.mainline.detect")
class KernelMainlineDetectIntent(Intent):
    """Intent pour détecter les noyaux mainline et modules externes."""

    def build_tasks(self):
        from fsdeploy.lib.function.kernel_mainline_detect import KernelMainlineDetectTask
        return [KernelMainlineDetectTask(
            id="kernel_mainline_detect",
            params=self.params,
            context=self.context,
        )]
