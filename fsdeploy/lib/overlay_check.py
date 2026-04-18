"""
Verification des overlayfs montes.
"""
from typing import List


def check_all_overlays() -> List[str]:
    """
    Verifie les overlayfs et retourne une liste de problemes.
    Retourne une liste vide si aucun probleme.
    """
    issues = []
    try:
        with open("/proc/mounts", "r") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 3 and parts[2] == "overlay":
                    mount_point = parts[1]
                    options = parts[3] if len(parts) > 3 else ""
                    if "lowerdir=" not in options:
                        issues.append(f"Overlay {mount_point} : lowerdir manquant")
    except (OSError, PermissionError):
        pass
    return issues
