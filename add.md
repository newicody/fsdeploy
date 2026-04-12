# add.md — Action 7.7 : lib/function/module/registry.py stub → re-export

**Date** : 2026-04-12

---

## Problème

Deux fichiers `ModuleRegistry` :
- `lib/function/module/registry.py` → **stub vide** (`class ModuleRegistry: pass`)
- `lib/modules/registry.py` → **version complète** (list_remote, install, uninstall, is_installed)

Le stub crée une confusion d'import : si quelqu'un importe depuis `function.module.registry`, il obtient un objet inutile sans méthodes.

---

## Correction

Remplacer le stub par un re-export :

```python
"""Backward compat — canonical location is lib/modules/registry."""
from fsdeploy.lib.modules.registry import ModuleRegistry
__all__ = ["ModuleRegistry"]
```

---

## Fichier Aider

```
fsdeploy/lib/function/module/registry.py
```

---

## Après

7.7 terminé. Prochaine : **7.2** (sync tests/ stale).
