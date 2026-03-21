"""
fsdeploy.function — Tasks exécutables.

Chaque task hérite de scheduler.model.task.Task et implémente :
  - required_resources() : ressources requises
  - required_locks() : verrous exclusifs/partagés
  - run() : logique métier

Organisation :
  detect/     — Détection environnement et rôles datasets
  live/       — Setup Debian Live (APT, DKMS, venv)
  boot/       — Génération init, construction initramfs
  kernel/     — Switch, install, compile kernels
  rootfs/     — Mount, switch, update overlay
  dataset/    — Mount, create, destroy, list datasets
  pool/       — Status, import, export, scrub pools
  snapshot/   — Create, rollback, send snapshots
  stream/     — YouTube streaming
  network/    — Configuration réseau
  service/    — Installation services système
  coherence/  — Vérification cohérence système
"""

# Re-exports pour imports simplifiés
from function.detect.environment import EnvironmentDetectTask
from function.detect.role_patterns import (
    ROLE_PATTERNS,
    detect_magic,
    scan_directory,
    compute_aggregate_confidence,
    get_role_color,
    get_role_emoji,
)

__all__ = [
    "EnvironmentDetectTask",
    "ROLE_PATTERNS",
    "detect_magic",
    "scan_directory",
    "compute_aggregate_confidence",
    "get_role_color",
    "get_role_emoji",
]
