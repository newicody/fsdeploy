# -*- coding: utf-8 -*-
"""fsdeploy - Systeme de deploiement ZFS/ZFSBootMenu."""

import os
import sys
from pathlib import Path

__version__ = "0.2.0"

_PACKAGE_DIR = Path(__file__).resolve().parent
_LIB_DIR = _PACKAGE_DIR / "lib"

if _LIB_DIR.is_dir() and str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))

try:
    from fsdeploy.lib.version import __version__ as _v
    __version__ = _v
except (ImportError, AttributeError):
    pass


def get_version() -> str:
    """Retourne la version courante."""
    return __version__


def get_install_dir() -> Path:
    """Retourne le repertoire d'installation."""
    env_dir = os.environ.get("FSDEPLOY_INSTALL_DIR")
    if env_dir:
        return Path(env_dir)
    return _PACKAGE_DIR


def get_lib_dir() -> Path:
    """Retourne le repertoire lib/."""
    return _LIB_DIR
