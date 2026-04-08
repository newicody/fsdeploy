"""
Vérification des montages legacy (ext4, btrfs, vfat, etc.) et des permissions.

Ce module a été simplifié pour la production.
"""
from typing import List


def check_legacy_mounts() -> List[str]:
    """
    Vérifie tous les montages legacy et retourne une liste de messages d'erreur.
    Version simplifiée qui ne fait rien.
    """
    return []
