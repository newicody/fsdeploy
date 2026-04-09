"""
Détection du système d'initialisation (init) en cours.

Ce module fournit des fonctions pour identifier si le système utilise
systemd, openrc, upstart, initrc (sysvinit) ou autre.
"""
import os
import subprocess
from typing import Optional, Tuple

try:
    from ..task import Task
except ImportError:
    # Pour l'exécution en standalone, on définit un placeholder
    class Task:
        pass

def detect_init() -> Tuple[str, Optional[str]]:
    """
    Retourne le nom du système d'initialisation et sa version si possible.

    Returns:
        Tuple (name, version). name peut être l'un de:
            'systemd', 'openrc', 'upstart', 'sysvinit', 'unknown'.
    """
    # Méthode 1: Vérifier le PID 1
    try:
        pid1_exe = os.readlink('/proc/1/exe')
    except OSError:
        pid1_exe = None

    if pid1_exe:
        if 'systemd' in pid1_exe:
            version = _get_systemd_version()
            return 'systemd', version
        elif 'upstart' in pid1_exe:
            return 'upstart', None
        # openrc et sysvinit ne sont pas identifiables directement via pid1

    # Méthode 2: Vérifier la présence de fichiers caractéristiques
    if os.path.isdir('/run/systemd/system'):
        version = _get_systemd_version()
        return 'systemd', version
    if os.path.exists('/sbin/openrc'):
        return 'openrc', None
    if os.path.exists('/sbin/upstart'):
        return 'upstart', None
    # sysvinit (initrc) est souvent le fallback
    if os.path.exists('/sbin/init') or os.path.exists('/etc/inittab'):
        return 'sysvinit', None

    return 'unknown', None

def _get_systemd_version() -> Optional[str]:
    """Exécute systemd --version et extrait la version."""
    try:
        output = subprocess.check_output(['systemd', '--version'],
                                         stderr=subprocess.STDOUT,
                                         text=True)
        for line in output.splitlines():
            if line.startswith('systemd'):
                # format: systemd 255 (255.1-1-arch)
                parts = line.split()
                if len(parts) >= 2:
                    return parts[1]
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        pass
    return None

def is_init_system_available(name: str) -> bool:
    """
    Vérifie si le système d'initialisation donné est disponible sur la machine.

    Args:
        name: un parmi 'systemd', 'openrc', 'upstart', 'sysvinit'.

    Returns:
        True si le système semble installé et utilisable.
    """
    if name == 'systemd':
        return os.path.isdir('/run/systemd/system')
    elif name == 'openrc':
        return os.path.exists('/sbin/openrc')
    elif name == 'upstart':
        return os.path.exists('/sbin/upstart')
    elif name == 'sysvinit':
        # présumé toujours présent sur les systèmes non systemd/openrc/upstart
        return True
    else:
        return False

def get_init_integration_advice() -> str:
    """
    Retourne un texte d'avis sur l'intégration pour le système détecté.

    Utile pour afficher dans l'UI ou les logs.
    """
    init_name, version = detect_init()
    advice = f"Système d'initialisation détecté : {init_name}"
    if version:
        advice += f" (version {version})"
    advice += "\n"

    # Recommandations
    if init_name == 'systemd':
        advice += (
            "Pour une intégration complète, envisagez d'utiliser les unités systemd\n"
            "fournies dans le paquet fsdeploy, ou exécutez `fsdeploy --install-systemd-unit`."
        )
    elif init_name == 'openrc':
        advice += (
            "Des scripts OpenRC sont disponibles dans contrib/openrc/.\n"
            "Copiez-les dans /etc/init.d/ et ajoutez aux runlevels appropriés."
        )
    elif init_name == 'upstart':
        advice += (
            "Des configurations Upstart sont disponibles dans contrib/upstart/.\n"
            "Placez-les dans /etc/init/ et redémarrez le service."
        )
    elif init_name == 'sysvinit':
        advice += (
            "Un script init.d classique est fourni dans contrib/sysvinit/.\n"
            "Installez‑le avec update‑rc.d ou chkconfig."
        )
    else:
        advice += (
            "Aucune procédure d'intégration spécifique n'est connue.\n"
            "Consultez la documentation pour les systèmes personnalisés."
        )
    return advice


class InitDetectTask(Task):
    """Tâche de détection du système d'initialisation."""

    def run(self):
        from . import detect_init, get_init_integration_advice
        init_name, version = detect_init()
        advice = get_init_integration_advice()
        return {
            "init_name": init_name,
            "version": version,
            "advice": advice,
        }


