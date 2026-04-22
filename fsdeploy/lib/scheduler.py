"""
fsdeploy.lib.scheduler — Runner Multi-Mode
============================================
Logique d'exécution des commandes selon le mode (chroot, local, ssh).
Gère les cages chroot et l'injection sudo.
"""

import os
import subprocess
import threading
from typing import Any, Optional

from fsdeploy.lib.log import get_logger

logger = get_logger(__name__)

BOOTSTRAP_ROOT = "/opt/fsdeploy/bootstrap"


def execute_from_config(
    section_name: str,
    config: Any,
    bridge: Any = None
) -> Optional[int]:
    """
    Exécute une section de configuration.

    Args:
        section_name: Nom de la section dans ConfigObj.
        config: Instance FsDeployConfig.
        bridge: Instance SchedulerBridge (optionnel, pour sudo).

    Returns:
        Code de retour de la commande, ou None si échec de préparation.
    """
    section = config.get(section_name, {})
    if not section:
        logger.error(f"Section '{section_name}' introuvable.")
        return None

    mode = section.get("mode", "local")
    root = section.get("root", "")
    command = section.get("command", "")
    use_sudo = section.get("sudo", False)

    if not command:
        logger.error(f"Section '{section_name}' : aucune commande.")
        return None

    if mode == "chroot":
        if not root:
            root = BOOTSTRAP_ROOT
        return _execute_chroot(root, command, use_sudo, bridge, section_name)
    elif mode == "ssh":
        logger.warning("Mode SSH non implémenté.")
        return None
    else:  # local
        return _execute_local(command, use_sudo, bridge, section_name)


def _execute_local(
    command: str,
    use_sudo: bool,
    bridge: Any,
    section_name: str
) -> Optional[int]:
    """Exécute une commande localement, avec sudo si nécessaire."""
    if use_sudo:
        return _run_with_sudo(command, bridge, section_name)
    else:
        logger.info(f"Exécution locale: {command}")
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True
        )
        if result.returncode != 0:
            logger.error(
                f"Échec (code {result.returncode}): {result.stderr}"
            )
        return result.returncode


def _execute_chroot(
    root: str,
    command: str,
    use_sudo: bool,
    bridge: Any,
    section_name: str
) -> Optional[int]:
    """Exécute une commande dans une cage chroot."""
    if not _prepare_cage(root):
        return None

    full_command = f"chroot {root} /bin/bash -c '{command}'"

    if use_sudo:
        ret = _run_with_sudo(full_command, bridge, section_name)
    else:
        logger.info(f"Exécution chroot: {full_command}")
        result = subprocess.run(
            full_command, shell=True, capture_output=True, text=True
        )
        ret = result.returncode
        if ret != 0:
            logger.error(
                f"Échec chroot (code {ret}): {result.stderr}"
            )

    _cleanup_cage(root)
    return ret


def _prepare_cage(root: str) -> bool:
    """
    Monte /dev, /proc, /sys dans la cage chroot.
    Retourne True si tout est OK.
    """
    mounts = [
        ("/dev", f"{root}/dev"),
        ("/proc", f"{root}/proc"),
        ("/sys", f"{root}/sys"),
    ]

    for src, dst in mounts:
        if not os.path.exists(dst):
            os.makedirs(dst, exist_ok=True)
        if os.path.ismount(dst):
            logger.debug(f"{dst} déjà monté.")
            continue
        ret = subprocess.run(
            ["sudo", "mount", "--bind", src, dst],
            capture_output=True, text=True
        )
        if ret.returncode != 0:
            logger.error(
                f"Échec montage {src} -> {dst}: {ret.stderr}"
            )
            return False
        logger.info(f"Monté {src} -> {dst}")
    return True


def _cleanup_cage(root: str) -> None:
    """Démonte les points montés dans la cage (force lazy)."""
    mounts = [
        f"{root}/dev",
        f"{root}/proc",
        f"{root}/sys",
    ]
    for mount_point in mounts:
        if os.path.ismount(mount_point):
            ret = subprocess.run(
                ["sudo", "umount", "-l", mount_point],
                capture_output=True, text=True
            )
            if ret.returncode != 0:
                logger.warning(
                    f"Échec démontage {mount_point}: {ret.stderr}"
                )
            else:
                logger.info(f"Démonté {mount_point}")
        else:
            logger.debug(f"{mount_point} n'est pas monté.")


def _run_with_sudo(
    command: str,
    bridge: Any,
    section_name: str
) -> Optional[int]:
    """
    Exécute une commande avec sudo en récupérant le mot de passe
    via le Bridge (UI) ou en console si bridge absent.
    """
    if bridge is None:
        # Fallback console
        password = input(
            f"Mot de passe sudo pour la section '{section_name}' : "
        )
    else:
        password = _request_sudo_via_bridge(bridge, section_name)
        if password is None:
            logger.error("Authentification sudo annulée.")
            return None

    try:
        process = subprocess.Popen(
            ["sudo", "-S"] + command.split(),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = process.communicate(input=f"{password}\n")
        if process.returncode != 0:
            logger.error(
                f"Sudo échoué (code {process.returncode}): {stderr}"
            )
        return process.returncode
    except Exception as e:
        logger.error(f"Erreur sudo: {e}")
        return None


def _request_sudo_via_bridge(
    bridge: Any,
    section_name: str
) -> Optional[str]:
    """
    Demande le mot de passe sudo via le Bridge (modal UI).
    Bloque jusqu'à la réponse. Retourne le mot de passe ou None.
    """
    event = threading.Event()
    result: dict[str, Optional[str]] = {"password": None}

    def callback(password: Optional[str]) -> None:
        result["password"] = password
        event.set()

    bridge.emit(
        "auth.sudo_request",
        section_id=section_name,
        action="Exécution de commande protégée",
        callback=callback
    )

    event.wait()
    return result["password"]
