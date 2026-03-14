"""
fsdeploy.core.install
======================
Installation des composants système de fsdeploy dans un rootfs cible.

Utilisable dans TROIS contextes sans modification :

  1. Debian Live (installateur)
     SystemInstaller(mountpoint="/mnt/gentoo", runner=runner)
     → installe dans le rootfs cible monté

  2. Système installé (post-boot, CLI)
     SystemInstaller(mountpoint="/", runner=runner)
     → installe/met à jour dans le système courant

  3. UI Textual (booted)
     SystemInstaller(mountpoint="/", runner=runner)
     → appelé depuis InstallScreen, log en temps réel via CommandLog

Le paramètre `mountpoint` est la seule différence entre les contextes.
Toutes les opérations passent par CommandRunner → log unifié.

API publique :
    from fsdeploy.core.install import SystemInstaller, InitSystem, InstallResult
    installer = SystemInstaller(cfg, runner, mountpoint=Path("/mnt/target"))
    result = installer.install_all()
    result = installer.install_cron()
    result = installer.install_service()
    result = installer.install_logrotate()
    result = installer.uninstall_all()
    status = installer.status()
"""

from fsdeploy.core.install.detect import InitSystem, detect_init_system
from fsdeploy.core.install.system import InstallResult, InstallStatus, SystemInstaller

__all__ = [
    "SystemInstaller",
    "InstallResult",
    "InstallStatus",
    "InitSystem",
    "detect_init_system",
]
