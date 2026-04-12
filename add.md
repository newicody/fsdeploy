# add.md — Action 6.0b : Remplacer `module_registry.py` par version complète

**Date** : 2026-04-12

---

## Problème

`lib/ui/screens/module_registry.py` est une ancienne version qui appelle `bridge.emit("moduleregistry.install", ...)` directement — pas de `ModuleRegistry` class, pas de `DataTable` avec statut install.

La version complète existe dans `tests/fsdeploy/lib/ui/screens/module_registry.py` : elle utilise `ModuleRegistry` de `lib/modules/registry.py` (créé en phase 1.3), a un `DataTable` fonctionnel, des bindings propres.

`app.py` charge depuis `module_registry` — donc ce fichier doit contenir la bonne implémentation.

---

## Correction

Remplacer `fsdeploy/lib/ui/screens/module_registry.py` par le contenu de `tests/fsdeploy/lib/ui/screens/module_registry.py` (version avec `from fsdeploy.lib.modules.registry import ModuleRegistry`, DataTable, refresh_modules, action_install, etc.)

---

## Fichier Aider

```
fsdeploy/lib/ui/screens/module_registry.py
```

---

## Après

6.0b terminé. Prochaine : **6.1** (imports cosmétiques navigation + tests) puis **6.2** (supprimer cross_compile_screen.py).
