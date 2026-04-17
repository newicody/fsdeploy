# add.md — Tâche 8.1 : Unification scheduler ↔ bridge global

> **Worker** : charger les fichiers listés, appliquer uniquement les changements décrits.

---

## Contexte

Le bridge TUI et le scheduler daemon sont deux instances séparées. Toutes les `bridge.emit()` partent dans le vide. C'est le blocage #1 — tant que ce n'est pas fixé, aucune fonctionnalité UI ne peut être testée ni aucun câblage vérifié (Phase 16).

---

## Fichiers à charger

### 1. `fsdeploy/lib/scheduler/core/scheduler.py`

**Bug** : `global_instance()` → imports cassés (`scheduler.runtime` n'existe pas), `Resolver()` sans security_resolver, `Executor()` sans runtime.

**Fix** :
- Imports : `scheduler.core.runtime.Runtime`, `scheduler.security.resolver.SecurityResolver`
- Construction : `rt = Runtime()` → `Executor(runtime=rt)` → `Resolver(security_resolver=SecurityResolver())` → `Scheduler(...)`
- Ajouter `set_global_instance(cls, instance)` classmethod

### 2. `fsdeploy/lib/daemon.py`

**Fix `_init_scheduler()`** : après construction, appeler `Scheduler.set_global_instance(self._scheduler)`

**Fix `_register_all_intents()`** : remplacer la lambda par factory qui propage `_bridge_ticket` :
```python
def _make_handler(cls, shared_ctx):
    def handler(event):
        ctx = dict(shared_ctx)
        ticket = event.params.get("_bridge_ticket")
        if ticket:
            ctx["_bridge_ticket"] = ticket
        return [cls(params=event.params, context=ctx)]
    return handler
```

### 3. `fsdeploy/lib/scheduler/bridge.py`

**Fix** : `default()`/`global_instance()` doit accéder au runtime via `Scheduler.global_instance().runtime`. Dans `poll()`, chercher `_bridge_ticket` dans `task.context` ET `task.params` (fallback).

### 4. `fsdeploy/lib/ui/bridge.py`

**Fix** : si `GlobalBridge.default()` échoue, ne pas créer d'instance locale silencieuse. Logger `"scheduler_bridge_unavailable"` et assigner un DummyBridge loggué.

---

## Critères d'acceptation

1. `python3 -c "from scheduler.core.scheduler import Scheduler; Scheduler.global_instance()"` → pas d'erreur (depuis `lib/`)
2. `python3 -m fsdeploy --debug` → log `scheduler_global_instance_set`
3. `cd lib && python3 test_run.py` → 3/3 tests pass
4. `bridge.poll()` retrouve les tickets via `task.context["_bridge_ticket"]`

---

## Ne pas toucher

Phases 9-16 sont toutes bloquées par 8.1. Une fois 8.1 fait, on peut tester le câblage existant et mesurer les gaps Phase 16 en live.
