#!/usr/bin/env python3
"""
Script pour la tâche 7.8 : supprimer le dossier tests/fsdeploy/.
Exécutez avec : python3 remove_tests_fsdeploy.py
"""
import os
import shutil
import sys

def main():
    target = "tests/fsdeploy"
    if os.path.exists(target):
        print(f"Suppression de {target}...")
        try:
            shutil.rmtree(target)
            print("✅ Dossier supprimé avec succès.")
        except Exception as e:
            print(f"❌ Erreur lors de la suppression : {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print(f"ℹ️ Le dossier {target} n'existe pas (déjà supprimé ?).")
        sys.exit(0)

if __name__ == "__main__":
    main()
