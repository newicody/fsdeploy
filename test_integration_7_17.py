#!/usr/bin/env python3
"""
Test d'intégration pour les étapes 7.13–7.16.

Vérifie que la configuration et le bridge sont correctement passés aux écrans,
que les scripts contrib ont les bonnes permissions et que la documentation est présente.
"""
import os
import sys
import stat
import subprocess
from pathlib import Path

def test_config_bridge():
    """Vérifie que ModuleRegistryScreen et autres écrans peuvent accéder à config et bridge."""
    # Importer les écrans et vérifier les attributs attendus
    try:
        from fsdeploy.lib.ui.screens.crosscompile import CrossCompileScreen
        from fsdeploy.lib.ui.screens.graph import GraphScreen
        from fsdeploy.lib.ui.screens.intentlog import IntentLogScreen
        from fsdeploy.lib.ui.screens.navigation import NavigationScreen
        from fsdeploy.lib.ui.screens.security import SecurityScreen
        from fsdeploy.lib.ui.screens.multiarch import MultiArchScreen
    except ImportError as e:
        print(f"ERREUR : impossible d'importer un écran : {e}")
        return False
    # Vérifie chaque classe
    for cls in [CrossCompileScreen, GraphScreen, IntentLogScreen,
                NavigationScreen, SecurityScreen, MultiArchScreen]:
        if not hasattr(cls, 'bridge'):
            print(f"La classe {cls.__name__} n'a pas la propriété bridge")
            return False
        if not hasattr(cls, 'config'):
            print(f"La classe {cls.__name__} n'a pas la propriété config")
            return False
    print("✓ Tous les écrans possèdent les propriétés bridge et config")
    return True

def test_contrib_permissions():
    """Vérifie que les scripts contrib ont les permissions correctes."""
    base = Path("fsdeploy/contrib")
    openrc_script = base / "openrc" / "fsdeploy.init"
    systemd_unit = base / "systemd" / "fsdeploy.service"
    if not openrc_script.exists():
        print(f"ATTENTION : {openrc_script} introuvable (peut‑être non créé)")
    else:
        st = openrc_script.stat()
        if not (st.st_mode & stat.S_IXUSR):
            print(f"ÉCHEC : {openrc_script} n'est pas exécutable")
            return False
        print(f"✓ {openrc_script} est exécutable")
    if not systemd_unit.exists():
        print(f"ATTENTION : {systemd_unit} introuvable (peut‑être non créé)")
    else:
        st = systemd_unit.stat()
        # doit être 644 (rw-r--r--)
        if (st.st_mode & 0o777) != 0o644:
            print(f"ÉCHEC : {systemd_unit} a les permissions {oct(st.st_mode & 0o777)}, attendu 644")
            return False
        print(f"✓ {systemd_unit} a les permissions correctes (644)")
    return True

def test_documentation():
    """Vérifie que CONTRIBUTING.md inclut une section sur contrib."""
    contrib_file = Path("CONTRIBUTING.md")
    if not contrib_file.exists():
        print("ÉCHEC : CONTRIBUTING.md n'existe pas")
        return False
    content = contrib_file.read_text(encoding='utf-8', errors='ignore')
    if 'contrib' not in content.lower():
        print("ÉCHEC : CONTRIBUTING.md ne mentionne pas contrib")
        return False
    print("✓ CONTRIBUTING.md contient une documentation sur contrib")
    return True

def main():
    print("Exécution du test d'intégration pour les étapes 7.13–7.16")
    success = True
    success = test_config_bridge() and success
    success = test_contrib_permissions() and success
    success = test_documentation() and success
    if success:
        print("\nTous les tests d'intégration ont réussi !")
        sys.exit(0)
    else:
        print("\nCertains tests d'intégration ont échoué.")
        sys.exit(1)

if __name__ == "__main__":
    main()
