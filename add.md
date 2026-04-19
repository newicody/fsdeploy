# add.md — 22.2 : Fix CLI cassée (sys.path régression 20.1)

## Diagnostic

`python3 -m fsdeploy` → "Erreur : impossible de trouver fsdeploy.cli"

Deux causes :
1. `__main__.py` ajoute `fsdeploy/` au sys.path au lieu du parent → `from fsdeploy.cli` cherche `fsdeploy/fsdeploy/cli.py` (supprimé en 20.1)
2. `__init__.py` ne met plus `lib/` dans sys.path → 36 fichiers avec des imports bare (`from scheduler.model.task import Task`) cassent

## A. Réécrire `fsdeploy/__main__.py`

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fsdeploy.__main__
==================
Point d'entree : python3 -m fsdeploy [OPTIONS] [COMMAND]
"""
import sys
import os
from pathlib import Path


def main():
    # Ajouter le PARENT de fsdeploy/ au sys.path
    # pour que 'from fsdeploy.cli import app' fonctionne
    _package_dir = Path(__file__).resolve().parent
    _parent_dir = _package_dir.parent
    _lib_dir = _package_dir / "lib"

    if str(_parent_dir) not in sys.path:
        sys.path.insert(0, str(_parent_dir))

    # Ajouter lib/ pour les imports bare (from scheduler.model.task import Task)
    # Utilise par 36 fichiers dans lib/
    if _lib_dir.is_dir() and str(_lib_dir) not in sys.path:
        sys.path.insert(0, str(_lib_dir))

    try:
        from fsdeploy.cli import app
    except ImportError as e:
        print(f"Erreur import CLI : {e}")
        sys.exit(1)

    sys.exit(app())


if __name__ == "__main__":
    main()
```

## B. Réécrire `fsdeploy/__init__.py`

Restaurer le setup sys.path pour `lib/` qui a été perdu en 20.1 :

```python
========
Systeme de deploiement ZFS/ZFSBootMenu depuis Debian Live.

Point d'entree : python3 -m fsdeploy
Le code metier vit dans lib/ — ce package gere le bootstrap.
"""

import os
import sys
from pathlib import Path

__version__ = "1.0.0"

# ── Path setup ────────────────────────────────────────────────────────
# Les modules scheduler/, function/, intents/, bus/ vivent dans lib/.
# On ajoute lib/ au sys.path pour que les imports bare fonctionnent :
#   from scheduler.core.scheduler import Scheduler
#   from bus import TimerSource

_PACKAGE_DIR = Path(__file__).resolve().parent
_LIB_DIR = _PACKAGE_DIR / "lib"

if _LIB_DIR.is_dir() and str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))

# ── Version ───────────────────────────────────────────────────────────
try:
    from fsdeploy.lib.version import __version__ as _v
    __version__ = _v
except (ImportError, AttributeError):
    pass


def get_version() -> str:
    return __version__


def get_install_dir() -> Path:
    env_dir = os.environ.get("FSDEPLOY_INSTALL_DIR")
    if env_dir:
        return Path(env_dir)
    return _PACKAGE_DIR


def get_lib_dir() -> Path:
    return _LIB_DIR
```

## Critères

1. `cd /opt/fsdeploy && python3 -m fsdeploy --help` → affiche l'aide typer (pas "Erreur")
2. `python3 -c "import fsdeploy; print(fsdeploy.get_lib_dir())"` → affiche le chemin lib/
3. `python3 -c "import fsdeploy; from scheduler.model.task import Task; print('OK')"` → OK (bare import fonctionne)
4. `grep "dirname.*dirname\|_parent_dir\|_lib_dir" fsdeploy/__main__.py` → parent + lib ajoutés
5. `grep "_LIB_DIR\|sys.path" fsdeploy/__init__.py` → setup lib/ restauré
