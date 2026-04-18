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
