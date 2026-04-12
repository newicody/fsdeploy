#!/usr/bin/env python3
"""
Script de test global pour fsdeploy.
Découvre et exécute tous les tests situés dans le répertoire tests/.
"""

import sys
import os
import pytest

def main() -> int:
    """Lance tous les tests du projet."""
    # S'assurer que nous sommes à la racine du projet
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Le répertoire des tests est à côté de ce script
    tests_dir = os.path.join(script_dir, "tests")
    if not os.path.isdir(tests_dir):
        print(f"ERREUR: répertoire tests introuvable ({tests_dir})", file=sys.stderr)
        return 1
    # Change de répertoire pour que les imports fonctionnent comme dans l'environnement de développement
    os.chdir(script_dir)
    # Exécute pytest avec des arguments par défaut (verbose, coloré)
    return pytest.main(["-v", "--tb=short", "--color=yes", tests_dir])

if __name__ == "__main__":
    sys.exit(main())
