# add.md — Action 6.0–6.2 : Unifier ModuleRegistryScreen + corriger imports

**Date** : 2026-04-12

---

## Problème

Trois fichiers pour le même écran :
- `lib/ui/screens/module_registry.py` → **stub** ("désactivé") — c'est ce que `app.py` charge
- `lib/ui/screens/moduleregistry_screen.py` → **ancienne version** (imports directs SchedulerBridge)
- `tests/fsdeploy/lib/ui/screens/module_registry.py` → **version complète** (avec ModuleRegistry)

`navigation.py` et `test_screens_integration.py` importent depuis `moduleregistry_screen` (ancien nom).

---

## Actions

### 1. `lib/ui/screens/module_registry.py` — remplacer stub par version complète

Copier le contenu de `tests/fsdeploy/lib/ui/screens/module_registry.py` (version avec `ModuleRegistry`, `DataTable`, install/refresh). C'est déjà le fichier que `app.py` charge.

### 2. `lib/ui/screens/moduleregistry_screen.py` — convertir en re-export

```python
"""Backward compat — canonical location is module_registry."""
from .module_registry import ModuleRegistryScreen
__all__ = ["ModuleRegistryScreen"]
```

### 3. `lib/ui/screens/navigation.py` — changer import

```python
# AVANT
from fsdeploy.lib.ui.screens.moduleregistry_screen import ModuleRegistryScreen
# APRÈS
from fsdeploy.lib.ui.screens.module_registry import ModuleRegistryScreen
```

### 4. `tests/fsdeploy/tests/ui/test_screens_integration.py` + `fsdeploy/tests/ui/test_screens_integration.py` — changer import

```python
# AVANT
from fsdeploy.lib.ui.screens.moduleregistry_screen import ModuleRegistryScreen
# APRÈS
from fsdeploy.lib.ui.screens.module_registry import ModuleRegistryScreen
```

---

## Fichiers Aider

```
fsdeploy/lib/ui/screens/module_registry.py
fsdeploy/lib/ui/screens/moduleregistry_screen.py
fsdeploy/lib/ui/screens/navigation.py
fsdeploy/tests/ui/test_screens_integration.py
tests/fsdeploy/tests/ui/test_screens_integration.py
tests/fsdeploy/lib/ui/screens/navigation.py
```

---

## Après

6.0–6.2 terminés. Prochaine : **6.3** (supprimer `cross_compile_screen.py`).
