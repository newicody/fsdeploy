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
