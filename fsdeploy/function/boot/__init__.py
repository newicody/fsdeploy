"""fsdeploy.function.boot — Boot et initramfs."""
from function.boot.init import BootInitTask
from function.boot.initramfs import InitramfsBuildTask

__all__ = ["BootInitTask", "InitramfsBuildTask"]
