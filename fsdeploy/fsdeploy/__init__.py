"""
fsdeploy
========
Système de déploiement ZFS/ZFSBootMenu depuis Debian Live.

Point d'entrée : python3 -m fsdeploy

Le code métier vit dans lib/ — ce package gère le bootstrap
(sys.path, version, exports publics).
"""

__version__ = "0.1.0"
__author__ = "newicody"
__license__ = "MIT"

import os
import sys
from pathlib import Path

# ── Path setup ────────────────────────────────────────────────────────────────
# Les modules scheduler/, function/, intents/, bus/ vivent dans lib/.
# On ajoute lib/ au sys.path pour que les imports bare fonctionnent :
#   from scheduler.core.scheduler import Scheduler
#   from bus import TimerSource

_PACKAGE_DIR = Path(__file__).resolve().parent
_LIB_DIR = _PACKAGE_DIR / "lib"

if _LIB_DIR.is_dir() and str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))

# ── Exports publics ──────────────────────────────────────────────────────────
# Import lazy pour ne pas casser si les dépendances ne sont pas installées.

def get_version() -> str:
    """Retourne la version courante."""
    return __version__


def get_install_dir() -> Path:
    """Retourne le répertoire d'installation."""
    env_dir = os.environ.get("FSDEPLOY_INSTALL_DIR")
    if env_dir:
        return Path(env_dir)
    return _PACKAGE_DIR


def get_lib_dir() -> Path:
    """Retourne le répertoire lib/ contenant le code métier."""
    return _LIB_DIR
