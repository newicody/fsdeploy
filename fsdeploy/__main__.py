#!/usr/bin/env python3
"""
Point d'entrée principal de fsdeploy.
Redirige vers le vrai point d'entrée typer (fsdeploy.__main__).
"""
import sys
import os

def main():
    # Ajouter le répertoire parent pour permettre l'import du package
    sys.path.insert(0, os.path.dirname(__file__))

    # Essayer d'importer l'app typer
    try:
        from fsdeploy.__main__ import app
    except ImportError:
        try:
            from fsdeploy.fsdeploy.__main__ import app
        except ImportError:
            print("Erreur : impossible de trouver le point d'entrée typer.")
            sys.exit(1)
    # Exécuter l'app typer avec les arguments actuels
    sys.exit(app())

if __name__ == "__main__":
    main()
