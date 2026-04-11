# add.md — Action 1.3 : Stub ModuleRegistry cassé

**Date** : 2026-04-11

---

## Problème

`lib/ui/screens/module_registry.py` fait :
```python
from fsdeploy.lib.modules.registry import ModuleRegistry
```

Mais `lib/function/module/registry.py` est un stub vide :
```python
"""Module de registre distant (désactivé)."""
```

→ `ImportError` au chargement de l'écran "modules" dans `app.py` screen_map.

Une implémentation complète existe dans `tests/fsdeploy/lib/modules/registry.py` avec données de démo et fallback.

---

## Correction

Copier l'implémentation `ModuleRegistry` de `tests/fsdeploy/lib/modules/registry.py` vers `fsdeploy/lib/modules/registry.py` (créer le fichier si nécessaire, avec `__init__.py`).

L'implémentation contient :
- `list_remote()` avec fallback démo si le registre distant est injoignable
- `is_installed(name)` vérifie le répertoire local
- `install(name)` / `uninstall(name)` basiques

---

## Fichiers Aider

```
fsdeploy/lib/modules/__init__.py
fsdeploy/lib/modules/registry.py
```

---

## Après

1.3 terminé. Prochaine : **2.0 Mode dry-run** (ou 1.4 synchro tests/ si prioritaire).
