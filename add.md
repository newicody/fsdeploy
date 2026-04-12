# add.md — Action 7.2 : Synchroniser tests/ avec lib/ (copies stale)

**Date** : 2026-04-12

---

## Problème

`tests/fsdeploy/` contient des copies miroir de `fsdeploy/` qui n'ont pas été mises à jour. Fichiers stale identifiés :

1. `tests/fsdeploy/lib/ui/screens/cross_compile_screen.py` — ancienne version avec `SchedulerBridge.default()` direct (lib/ l'a supprimé)
2. `tests/fsdeploy/lib/ui/screens/moduleregistry_screen.py` — ancienne version avec bridge direct (lib/ = re-export)
3. `tests/fsdeploy/lib/function/module/registry.py` — ancien stub `pass` (lib/ = re-export)

---

## Corrections

### 1. `cross_compile_screen.py` → re-export

```python
"""Backward compat — canonical location is crosscompile."""
from .crosscompile import CrossCompileScreen
__all__ = ["CrossCompileScreen"]
```

### 2. `moduleregistry_screen.py` → re-export

```python
"""Backward compat — canonical location is module_registry."""
from .module_registry import ModuleRegistryScreen
__all__ = ["ModuleRegistryScreen"]
```

### 3. `function/module/registry.py` → re-export

```python
"""Backward compat — canonical location is lib/modules/registry."""
from fsdeploy.lib.modules.registry import ModuleRegistry
__all__ = ["ModuleRegistry"]
```

---

## Fichiers Aider

```
tests/fsdeploy/lib/ui/screens/cross_compile_screen.py
tests/fsdeploy/lib/ui/screens/moduleregistry_screen.py
tests/fsdeploy/lib/function/module/registry.py
```

---

## Après

7.2 terminé. Prochaine : **7.4** (README.md curl → dev).
