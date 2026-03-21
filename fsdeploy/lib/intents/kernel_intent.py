"""
fsdeploy.intents.kernel_intent
================================
Intents pour les operations kernel et initramfs declenchees par la TUI.

Events geres :
  kernel.list          → liste les kernels disponibles dans boot_mount
  kernel.switch        → bascule le kernel actif (symlinks)
  kernel.install       → installe un kernel depuis .deb ou fichier
  kernel.compile       → compile un kernel depuis les sources
  initramfs.build      → construit un initramfs (dracut ou cpio)
  initramfs.list       → liste les initramfs disponibles
  boot.init.generate   → genere le script /init pour l'initramfs
"""

from typing import Any

from scheduler.model.intent import Intent
from scheduler.model.task import Task
from scheduler.model.resource import Resource, KERNEL, INITRAMFS
from scheduler.model.lock import Lock
from scheduler.core.registry import register_intent
from scheduler.security.decorator import security


# ═══════════════════════════════════════════════════════════════════
# TASKS SUPPLEMENTAIRES
# ═══════════════════════════════════════════════════════════════════

@security.kernel.list
class KernelListTask(Task):
    """Liste les kernels disponibles dans le repertoire de boot."""

    def run(self) -> list[dict[str, Any]]:
        from pathlib import Path
        from packaging.version import Version, InvalidVersion

        boot_path = Path(self.params.get("boot_path", "/boot"))
        kernels = []

        # Chercher les vmlinuz
        for pattern in ("vmlinuz-*", "bzImage-*", "vmlinuz*"):
            for f in boot_path.glob(pattern):
                if f.is_file() or f.is_symlink():
                    name = f.name
                    # Extraire la version
                    version = ""
                    for prefix in ("vmlinuz-", "bzImage-"):
                        if name.startswith(prefix):
                            version = name[len(prefix):]
                            break

                    # Verifier si c'est le symlink actif
                    active_link = boot_path / "vmlinuz"
                    is_active = (active_link.is_symlink() and
                                 active_link.resolve() == f.resolve())

                    # Chercher initramfs associe
                    initramfs = ""
                    for ipattern in (f"initramfs-{version}.img",
                                     f"initrd.img-{version}"):
                        ip = boot_path / ipattern
                        if ip.exists():
                            initramfs = ip.name
                            break

                    # Chercher modules
                    modules_path = f"/lib/modules/{version}"
                    has_modules = Path(modules_path).is_dir()

                    kernels.append({
                        "file": name,
                        "version": version,
                        "path": str(f),
                        "size": f.stat().st_size if f.exists() else 0,
                        "active": is_active,
                        "initramfs": initramfs,
                        "has_modules": has_modules,
                    })

        # Trier par version (plus recente en premier)
        def sort_key(k):
            try:
                return Version(k["version"])
            except (InvalidVersion, TypeError):
                return Version("0")
        kernels.sort(key=sort_key, reverse=True)

        return kernels


@security.initramfs.list
class InitramfsListTask(Task):
    """Liste les initramfs disponibles."""

    def run(self) -> list[dict[str, Any]]:
        from pathlib import Path

        boot_path = Path(self.params.get("boot_path", "/boot"))
        images = []

        for pattern in ("initramfs-*.img", "initrd.img-*",
                         "initramfs*.img", "initrd-*"):
            for f in boot_path.glob(pattern):
                if f.is_file():
                    # Extraire la version
                    name = f.name
                    version = ""
                    for prefix in ("initramfs-", "initrd.img-", "initrd-"):
                        if name.startswith(prefix):
                            rest = name[len(prefix):]
                            version = rest.replace(".img", "")
                            break

                    # Actif ?
                    active_link = boot_path / "initramfs.img"
                    is_active = (active_link.is_symlink() and
                                 active_link.resolve() == f.resolve())

                    images.append({
                        "file": name,
                        "version": version,
                        "path": str(f),
                        "size": f.stat().st_size,
                        "active": is_active,
                    })

        images.sort(key=lambda x: x["version"], reverse=True)
        return images


# ═══════════════════════════════════════════════════════════════════
# INTENTS
# ═══════════════════════════════════════════════════════════════════

@register_intent("kernel.list")
class KernelListIntent(Intent):
    """Event: kernel.list → KernelListTask"""
    def build_tasks(self):
        return [KernelListTask(
            id="kernel_list", params=self.params, context=self.context)]


@register_intent("kernel.switch")
class KernelSwitchIntent(Intent):
    """Event: kernel.switch → KernelSwitchTask"""
    def build_tasks(self):
        from function.kernel.switch import KernelSwitchTask
        version = self.params.get("version", "")
        if not version:
            return []
        return [KernelSwitchTask(
            id=f"switch_{version}",
            params=self.params, context=self.context)]


@register_intent("kernel.install")
class KernelInstallIntent(Intent):
    """Event: kernel.install → KernelInstallTask"""
    def build_tasks(self):
        from function.kernel.switch import KernelInstallTask
        return [KernelInstallTask(
            id="kernel_install", params=self.params, context=self.context)]


@register_intent("kernel.compile")
class KernelCompileIntent(Intent):
    """Event: kernel.compile → KernelCompileTask"""
    def build_tasks(self):
        from function.kernel.switch import KernelCompileTask
        return [KernelCompileTask(
            id="kernel_compile", params=self.params, context=self.context)]


@register_intent("initramfs.build")
class InitramfsBuildIntent(Intent):
    """Event: initramfs.build → InitramfsBuildTask"""
    def build_tasks(self):
        from function.boot.initramfs import InitramfsBuildTask
        return [InitramfsBuildTask(
            id="initramfs_build", params=self.params, context=self.context)]


@register_intent("initramfs.list")
class InitramfsListIntent(Intent):
    """Event: initramfs.list → InitramfsListTask"""
    def build_tasks(self):
        return [InitramfsListTask(
            id="initramfs_list", params=self.params, context=self.context)]


@register_intent("boot.init.generate")
class BootInitGenerateIntent(Intent):
    """Event: boot.init.generate → BootInitTask"""
    def build_tasks(self):
        from function.boot.init import BootInitTask
        return [BootInitTask(
            id="boot_init_gen", params=self.params, context=self.context)]
