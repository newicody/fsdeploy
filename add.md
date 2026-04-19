# add.md — 22.3 : Fix `fsdeploy/__init__.py` (SyntaxError)

Le worker a échoué 3 fois à écrire ce fichier. Utiliser cette commande bash exacte :

```bash
cat > fsdeploy/__init__.py << 'ENDOFFILE'
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
ENDOFFILE
```

Puis vérifier :

```bash
python3 -c "import ast; ast.parse(open('fsdeploy/__init__.py').read()); print('OK')"
wc -l fsdeploy/__init__.py  # doit être >= 38
git add fsdeploy/__init__.py
git commit -m "fix: restaure __init__.py complet (sys.path + docstring)"
```

## Alternative

Le fichier corrigé est aussi fourni en téléchargement sous le nom `fsdeploy_init.py`. Le copier manuellement :

```bash
cp fsdeploy_init.py fsdeploy/__init__.py
```

## Critères

1. `python3 -c "import ast; ast.parse(open('fsdeploy/__init__.py').read())"` → pas de SyntaxError
2. `wc -l fsdeploy/__init__.py` → 38+ lignes
3. `grep "_LIB_DIR" fsdeploy/__init__.py` → sys.path setup présent
