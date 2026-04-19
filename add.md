# add.md — 22.3 : Fix `fsdeploy/__init__.py` tronqué (SyntaxError)

## Bug

Le fichier fait 3 lignes avec une docstring `"""` non fermée :
```
# -*- coding: utf-8 -*-
"""
fsdeploy
```

`import fsdeploy` → `SyntaxError: unterminated triple-quoted string literal`

## Fix

Écraser le fichier `fsdeploy/__init__.py` avec le contenu exact suivant (44 lignes) :

```python
# -*- coding: utf-8 -*-
"""
fsdeploy - Systeme de deploiement ZFS/ZFSBootMenu.
"""

import os
import sys
from pathlib import Path

__version__ = "1.0.0"

# Path setup : ajouter lib/ au sys.path pour les imports bare
# (from scheduler.model.task import Task) utilises par 36 fichiers
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
```

**ATTENTION** : le fichier doit faire exactement 44 lignes. Vérifier que la docstring ligne 3 est bien fermée par `"""` ligne 4. Ne PAS tronquer le fichier.

## Critères

1. `python3 -c "import ast; ast.parse(open('fsdeploy/__init__.py').read()); print('SYNTAX OK')"` → SYNTAX OK
2. `wc -l fsdeploy/__init__.py` → au moins 40 lignes
3. `PYTHONPATH=. python3 -c "import fsdeploy; print(fsdeploy.__version__)"` → pas de SyntaxError
4. `PYTHONPATH=. python3 -c "import fsdeploy; print(fsdeploy.get_lib_dir())"` → affiche un chemin
