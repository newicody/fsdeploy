# add.md — Action 6.1+6.2 : Imports cosmétiques + supprimer stub

**Date** : 2026-04-12

---

## 6.1 — Imports cosmétiques

`navigation.py` et `test_screens_integration.py` importent encore depuis `moduleregistry_screen` (fonctionne via re-export, mais devrait pointer vers le canonique).

### Changement dans chaque fichier :

```python
# AVANT
from fsdeploy.lib.ui.screens.moduleregistry_screen import ModuleRegistryScreen
# APRÈS
from fsdeploy.lib.ui.screens.module_registry import ModuleRegistryScreen
```

Fichiers concernés :
- `fsdeploy/lib/ui/screens/navigation.py`
- `tests/fsdeploy/lib/ui/screens/navigation.py`
- `fsdeploy/tests/ui/test_screens_integration.py`
- `tests/fsdeploy/tests/ui/test_screens_integration.py`

---

## 6.2 — Supprimer stub `cross_compile_screen.py`

`fsdeploy/lib/ui/screens/cross_compile_screen.py` ne contient qu'un `raise ImportError`. Plus personne ne l'importe (navigation.py corrigé en 1.2). Supprimer.

`scripts/cleanup.sh` contient déjà la commande `rm` — il suffit d'exécuter ou de supprimer manuellement.

---

## Fichiers Aider

```
fsdeploy/lib/ui/screens/navigation.py
fsdeploy/tests/ui/test_screens_integration.py
tests/fsdeploy/lib/ui/screens/navigation.py
tests/fsdeploy/tests/ui/test_screens_integration.py
fsdeploy/lib/ui/screens/cross_compile_screen.py   (supprimer)
```

---

## Après

Phase 6 terminée. PLAN complet.
