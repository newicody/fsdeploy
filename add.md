# add.md — Action 7.2 : Sync 2 écrans stale dans tests/

**Date** : 2026-04-13

---

## Problème

`tests/fsdeploy/lib/function/module/registry.py` ✅ déjà corrigé (re-export).

Restent 2 fichiers avec `SchedulerBridge.default()` direct :

1. `tests/fsdeploy/lib/ui/screens/cross_compile_screen.py` — ancienne version complète
2. `tests/fsdeploy/lib/ui/screens/moduleregistry_screen.py` — ancienne version complète

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

---

## Fichiers Aider

```
tests/fsdeploy/lib/ui/screens/cross_compile_screen.py
tests/fsdeploy/lib/ui/screens/moduleregistry_screen.py
```

---

## Après

7.2 terminé. Prochaine : **7.4** (README.md curl → dev).
