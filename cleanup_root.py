#!/usr/bin/env python3
"""
Script de nettoyage racine et suppression du double nesting fsdeploy/fsdeploy/
Conforme à add.md.
"""
import os
import shutil
import sys

def main():
    root = "."
    # 1. Supprimer les 6 fichiers racine orphelins
    orphan_files = [
        "check_imports_7.8.py",
        "cleanup_contrib.sh",
        "cleanup_lib_ui.sh",
        "remove_tests_fsdeploy.py",
        "test_all.py",
        "test_integration_7_17.py",
    ]
    for f in orphan_files:
        path = os.path.join(root, f)
        if os.path.exists(path):
            print(f"Suppression de {path}")
            os.unlink(path)
        else:
            print(f"Fichier {path} non présent (ignoré)")
    # 2. Résoudre double nesting fsdeploy/fsdeploy/
    nested_dir = os.path.join(root, "fsdeploy", "fsdeploy")
    if os.path.exists(nested_dir):
        print(f"Suppression du répertoire double {nested_dir}")
        shutil.rmtree(nested_dir)
    else:
        print(f"Répertoire {nested_dir} non présent (ignoré)")
    # Vérification que fsdeploy importe toujours
    try:
        import fsdeploy
        print("Import fsdeploy réussi.")
    except ImportError as e:
        print(f"ERREUR: import fsdeploy a échoué: {e}", file=sys.stderr)
        sys.exit(1)
    print("Nettoyage terminé avec succès.")

if __name__ == "__main__":
    main()
