# add.md — 22.1 : Fix __main__.py — CLI cassé

## Bug

`python3 -m fsdeploy` affiche "Erreur : impossible de trouver le point d'entrée typer." et quitte.

Cause : `fsdeploy/__main__.py` essaie d'importer `app` depuis `fsdeploy.fsdeploy.__main__` qui a été supprimé en 20.1. L'app typer est définie dans `fsdeploy/cli.py`.

## Fix

Réécrire `fsdeploy/__main__.py` :

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


def main():
    sys.path.insert(0, os.path.dirname(__file__))
    try:
        from fsdeploy.cli import app
    except ImportError:
        print("Erreur : impossible de trouver fsdeploy.cli")
        sys.exit(1)
    sys.exit(app())


if __name__ == "__main__":
    main()
```

## Critères

1. `grep "fsdeploy.fsdeploy" fsdeploy/__main__.py` → aucun résultat
2. `grep "from fsdeploy.cli import app" fsdeploy/__main__.py` → présent
3. `python3 -m fsdeploy --help` → affiche l'aide typer (pas "Erreur")
