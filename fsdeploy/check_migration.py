#!/usr/bin/env python3
"""
Script pour vérifier la migration des écrans vers bridge.emit.
Usage : python check_migration.py
"""
import os
import re
import sys

def main():
    screens_dir = "fsdeploy/lib/ui/screens"
    if not os.path.isdir(screens_dir):
        print(f"ERREUR: Répertoire non trouvé: {screens_dir}")
        sys.exit(1)
    
    for root, dirs, files in os.walk(screens_dir):
        for fname in files:
            if fname.endswith(".py"):
                path = os.path.join(root, fname)
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                # Recherche d'imports de bridge
                if re.search(r'from\s+\.bridge\s+import\s+SchedulerBridge|import\s+\.bridge', content):
                    has_import = True
                else:
                    has_import = False
                # Recherche d'initialisation de self.bridge
                if 'self.bridge' in content and ('SchedulerBridge' in content or 'bridge' in content):
                    has_init = True
                else:
                    has_init = False
                # Recherche d'appel à bridge.emit
                if 'bridge.emit' in content:
                    has_emit = True
                else:
                    has_emit = False
                print(f"{fname}: import={has_import}, init={has_init}, emit={has_emit}")
                if not (has_import or has_init or has_emit):
                    print(f"  -> Possiblement non migré")

if __name__ == "__main__":
    main()
