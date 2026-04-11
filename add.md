# add.md — Action 2.0 : Mode dry-run — propagation

**Date** : 2026-04-11

---

## État actuel

Le dry-run est **partiellement câblé** :
- ✅ `__main__.py` : option `--dry-run`/`-n`, stocké dans `state.dry_run`
- ✅ `config.py` : `state.config.set("env.dry_run", True)` dans `_load_config()`
- ✅ `Task.run_cmd()` : accepte `dry_run=True` et retourne `[dry-run]` sans exécuter

**Ce qui manque** : quand `state.dry_run=True`, chaque `task.run_cmd()` est toujours appelé avec `dry_run=False` par défaut. Aucune task ne lit `self.context.get("dry_run")` ou `self.params.get("dry_run")` pour le propager.

---

## Correction

1. **`daemon.py`** : dans `_register_all_intents()` ou au lancement, injecter `dry_run` dans le contexte global du scheduler pour qu'il soit propagé à chaque intent/task.

2. **`task.py`** : modifier `run_cmd()` pour lire `self.context.get("dry_run", False)` comme valeur par défaut du paramètre `dry_run`, au lieu de `False` :

```python
def run_cmd(self, cmd, ..., dry_run=None):
    if dry_run is None:
        dry_run = self.context.get("dry_run", False) or self.params.get("dry_run", False)
    ...
```

3. **`executor.py`** : quand le scheduler exécute une task, injecter `dry_run` dans `task.context` depuis la config globale.

---

## Fichiers Aider

```
fsdeploy/lib/scheduler/model/task.py
fsdeploy/lib/daemon.py
```

---

## Après

2.0 terminé. Prochaine : **2.1** (health-check au démarrage).
