# -*- coding: utf-8 -*-
"""
fsdeploy.intents.kernel_intent
================================
Intents pour les operations kernel et initramfs declenchees par la TUI.

Events geres :
  kernel.registry.scan → inventaire cross-dataset de tous les kernels
  kernel.list          → liste les kernels disponibles dans boot_mount
  kernel.switch        → bascule le kernel actif (symlinks)
  kernel.provision     → provisionne un kernel depuis source vers staging
  kernel.unprovision   → retire un kernel du staging
  kernel.install       → installe un kernel depuis .deb ou fichier
  kernel.compile       → compile un kernel depuis les sources
  initramfs.build      → construit un initramfs (dracut ou cpio)
  initramfs.list       → liste les initramfs disponibles
  boot.init.generate   → genere le script /init pour l'initramfs
  zbm.validate         → validation pre-vol ZFSBootMenu
"""

from typing import Any

from scheduler.model.intent import Intent
from scheduler.model.task import Task
from scheduler.model.resource import Resource, KERNEL, INITRAMFS
from scheduler.model.lock import Lock
from scheduler.core.registry import register_intent
from scheduler.security.decorator import security


# ===================================================================
# TASKS SUPPLEMENTAIRES (inline, legeres)
# ===================================================================

@security.kernel.list
class KernelListTask(Task):
    """Liste les kernels disponibles dans le repertoire de boot."""

    def run(self) -> list[dict[str, Any]]:
        from pathlib import Path
        import hashlib

        boot_path = Path(self.params.get("boot_path", ""))
        if not boot_path or not boot_path.is_dir():
            return []

        # Prefixes depuis config (aucun en dur)
        kernel_prefixes = self.params.get("kernel_prefixes",
                                          ["vmlinuz-", "vmlinux-", "bzImage-"])
        initramfs_prefixes = self.params.get("initramfs_prefixes",
                                              ["initramfs-", "initrd.img-", "initrd-"])

        kernels = []

        for pfx in kernel_prefixes:
            for f in sorted(boot_path.glob(f"{pfx}*")):
                if not f.is_file():
                    continue
                name = f.name
                # Extraire version
                version = name
                for p in kernel_prefixes:
                    if version.startswith(p):
                        version = version[len(p):]
                        break

                # Verifier si actif (symlink vmlinuz pointe vers ce fichier)
                vmlinuz_link = boot_path / "vmlinuz"
                is_active = False
                if vmlinuz_link.is_symlink():
                    try:
                        is_active = vmlinuz_link.resolve() == f.resolve()
                    except OSError:
                        pass

                # Chercher initramfs correspondant
                initramfs_name = ""
                for ipfx in initramfs_prefixes:
                    for ext in (".img", ""):
                        candidate = boot_path / f"{ipfx}{version}{ext}"
                        if candidate.exists():
                            initramfs_name = candidate.name
                            break
                    if initramfs_name:
                        break

                # Chercher modules
                has_modules = False
                for mod_base in (boot_path, boot_path.parent):
                    mod_dir = mod_base / "lib" / "modules" / version
                    if mod_dir.is_dir():
                        has_modules = True
                        break

                # MD5
                md5 = ""
                try:
                    h = hashlib.md5()
                    with f.open("rb") as fh:
                        for chunk in iter(lambda: fh.read(65536), b""):
                            h.update(chunk)
                    md5 = h.hexdigest()
                except OSError:
                    pass

                kernels.append({
                    "file": name,
                    "version": version,
                    "path": str(f),
                    "size": f.stat().st_size,
                    "active": is_active,
                    "initramfs": initramfs_name,
                    "has_modules": has_modules,
                    "md5": md5,
                })

        # Trier : actif en premier, puis par version desc
        kernels.sort(key=lambda k: (not k["active"], k["version"]),
                     reverse=False)
        return kernels


@security.kernel.list
class InitramfsListTask(Task):
    """Liste les initramfs disponibles."""

    def run(self) -> list[dict[str, Any]]:
        from pathlib import Path

        boot_path = Path(self.params.get("boot_path", ""))
        if not boot_path or not boot_path.is_dir():
            return []

        initramfs_prefixes = self.params.get("initramfs_prefixes",
                                              ["initramfs-", "initrd.img-", "initrd-"])

        images = []
        for pfx in initramfs_prefixes:
            for f in sorted(boot_path.glob(f"{pfx}*")):
                if not f.is_file():
                    continue
                name = f.name
                version = name
                for p in initramfs_prefixes:
                    if version.startswith(p):
                        version = version[len(p):]
                        break
                # Retirer .img
                for suffix in (".img", ".cpio", ".cpio.gz"):
                    if version.endswith(suffix):
                        version = version[:-len(suffix)]
                        break

                active_link = boot_path / "initramfs.img"
                is_active = False
                if active_link.is_symlink():
                    try:
                        is_active = active_link.resolve() == f.resolve()
                    except OSError:
                        pass

                images.append({
                    "file": name,
                    "version": version,
                    "path": str(f),
                    "size": f.stat().st_size,
                    "active": is_active,
                })

        images.sort(key=lambda x: x["version"], reverse=True)
        return images


# ===================================================================
# INTENTS — REGISTRY
# ===================================================================

@register_intent("kernel.registry.scan")
class KernelRegistryScanIntent(Intent):
    """Event: kernel.registry.scan -> KernelRegistryScanTask"""
    def build_tasks(self):
        from function.kernel.registry import KernelRegistryScanTask
        return [KernelRegistryScanTask(
            id="kernel_registry_scan",
            params=self.params, context=self.context)]


# ===================================================================
# INTENTS — LIST
# ===================================================================

@register_intent("kernel.list")
class KernelListIntent(Intent):
    """Event: kernel.list -> KernelListTask"""
    def build_tasks(self):
        return [KernelListTask(
            id="kernel_list", params=self.params, context=self.context)]


# ===================================================================
# INTENTS — PROVISION / UNPROVISION
# ===================================================================

@register_intent("kernel.provision")
class KernelProvisionIntent(Intent):
    """Event: kernel.provision -> KernelProvisionTask"""
    def build_tasks(self):
        from function.kernel.provision import KernelProvisionTask
        return [KernelProvisionTask(
            id="kernel_provision",
            params=self.params, context=self.context)]


@register_intent("kernel.unprovision")
class KernelUnprovisionIntent(Intent):
    """Event: kernel.unprovision -> KernelUnprovisionTask"""
    def build_tasks(self):
        from function.kernel.provision import KernelUnprovisionTask
        return [KernelUnprovisionTask(
            id="kernel_unprovision",
            params=self.params, context=self.context)]


# ===================================================================
# INTENTS — SWITCH
# ===================================================================

@register_intent("kernel.switch")
class KernelSwitchIntent(Intent):
    """Event: kernel.switch -> KernelSwitchTask"""
    def build_tasks(self):
        from function.kernel.switch import KernelSwitchTask
        version = self.params.get("version", "")
        if not version:
            return []
        return [KernelSwitchTask(
            id=f"switch_{version}",
            params=self.params, context=self.context)]


# ===================================================================
# INTENTS — INSTALL / COMPILE
# ===================================================================

@register_intent("kernel.install")
class KernelInstallIntent(Intent):
    """Event: kernel.install -> KernelInstallTask"""
    def build_tasks(self):
        from function.kernel.switch import KernelInstallTask
        return [KernelInstallTask(
            id="kernel_install", params=self.params, context=self.context)]


@register_intent("kernel.compile")
class KernelCompileIntent(Intent):
    """Event: kernel.compile -> KernelCompileTask"""
    def build_tasks(self):
        from function.kernel.switch import KernelCompileTask
        return [KernelCompileTask(
            id="kernel_compile", params=self.params, context=self.context)]


# ===================================================================
# INTENTS — INITRAMFS
# ===================================================================

@register_intent("initramfs.build")
class InitramfsBuildIntent(Intent):
    """Event: initramfs.build -> InitramfsBuildTask"""
    def build_tasks(self):
        from function.boot.initramfs import InitramfsBuildTask
        return [InitramfsBuildTask(
            id="initramfs_build", params=self.params, context=self.context)]


@register_intent("initramfs.list")
class InitramfsListIntent(Intent):
    """Event: initramfs.list -> InitramfsListTask"""
    def build_tasks(self):
        return [InitramfsListTask(
            id="initramfs_list", params=self.params, context=self.context)]


@register_intent("boot.init.generate")
class BootInitGenerateIntent(Intent):
    """Event: boot.init.generate -> BootInitTask"""
    def build_tasks(self):
        from function.boot.init import BootInitTask
        return [BootInitTask(
            id="boot_init_gen", params=self.params, context=self.context)]


# ===================================================================
# INTENTS — ZBM VALIDATE (pre-vol)
# ===================================================================

@register_intent("zbm.validate")
class ZBMValidateIntent(Intent):
    """Event: zbm.validate -> ZBMPreflightTask"""
    def build_tasks(self):
        from function.zbm.validate import ZBMPreflightTask
        return [ZBMPreflightTask(
            id="zbm_preflight",
            params=self.params, context=self.context)]
