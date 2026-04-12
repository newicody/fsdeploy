# add.md — Action 6.0b : Remplacer `module_registry.py` par version complète

**Date** : 2026-04-12

---

## Problème

`lib/ui/screens/module_registry.py` utilise `bridge.emit("moduleregistry.install", ...)` directement — pas de `ModuleRegistry` class, pas de `DataTable` avec statut install.

La version complète existe dans `tests/fsdeploy/lib/ui/screens/module_registry.py` : elle utilise `ModuleRegistry` de `lib/modules/registry.py` (créé en phase 1.3), a un `DataTable` fonctionnel, des bindings propres.

`app.py` charge depuis `module_registry` — donc ce fichier doit contenir la bonne implémentation.

---

## Correction

Remplacer `fsdeploy/lib/ui/screens/module_registry.py` par le contenu de `tests/fsdeploy/lib/ui/screens/module_registry.py` :
- Import `from fsdeploy.lib.modules.registry import ModuleRegistry`
- `__init__` crée `self.registry = ModuleRegistry()`
- `refresh_modules()` appelle `self.registry.list_remote()`
- `action_install()` appelle `self.registry.install(name)`
- DataTable avec colonnes Nom/Version/Description/Statut
- Bindings : escape, r=refresh, i=install

---

## Fichier Aider

```
fsdeploy/lib/ui/screens/module_registry.py
```

---

## Après

6.0b terminé. Prochaine : **6.1** (imports cosmétiques) puis **6.2** (supprimer cross_compile_screen.py).
