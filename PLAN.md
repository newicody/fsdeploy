# add.md — Tâche 8.1b : Finaliser unification scheduler

> **Worker** : charger les fichiers listés, appliquer les changements décrits.

---

## Ce qui a été fait (8.1a ✅)

- `Scheduler.set_global_instance()` ajouté
- `daemon._init_scheduler()` appelle `set_global_instance` + log
- `daemon._register_all_intents()` utilise `_make_handler()` avec propagation `_bridge_ticket`
- `bridge.py` : `BridgeEvent`, `submit_event()` avec ticket, `poll()` cherche dans `context` ET `params`
- `model/event.py` : `BridgeEvent` + `register_bridge_event_handler()`
- `model/runtime.py` : `get_global_runtime()` singleton

## Ce qui reste cassé (3 problèmes)

### Problème 1 : Import path faux

`scheduler.py global_instance()` fait :
```python
from fsdeploy.lib.scheduler.runtime import Runtime
```
Ce module n'existe pas comme ça. `Runtime` est dans `scheduler.core.runtime` (quand `lib/` est dans sys.path) ou `fsdeploy.lib.scheduler.core.runtime` (en absolute). Le même bug est reproduit dans le nouveau `fsdeploy/__main__.py`.

### Problème 2 : Deux `__main__.py` concurrents

1. **`fsdeploy/__main__.py`** (NOUVEAU, argparse) — crée `Scheduler(Resolver(), Executor(), runtime)` **sans SecurityResolver**, **sans bus**, **sans intent registration**, **sans daemon**. Bypass total de l'architecture.
2. **`fsdeploy/fsdeploy/__main__.py`** (typer) — appelle `FsDeployDaemon` qui fait l'init propre avec SecurityResolver, bus, intents, TUI avec restart.

`python3 -m fsdeploy` résout vers le **premier** (package `fsdeploy/`), pas le deuxième. Donc le chemin daemon (le bon) n'est jamais appelé.

### Problème 3 : `pyproject.toml` entry point faux

```toml
[project.scripts]
fsdeploy = "lib.__main__:main"
```
`lib` n'est pas un package importable — ça ne résout pas.

---

## Fichiers à charger

### 1. `fsdeploy/lib/scheduler/core/scheduler.py`

**Fix** : dans `global_instance()`, remplacer :
```python
from fsdeploy.lib.scheduler.runtime import Runtime
```
par :
```python
from scheduler.core.runtime import Runtime
```
(Cohérent avec le reste du fichier qui utilise `scheduler.*` relatif, car `lib/` est dans sys.path via daemon.)

L'import `fsdeploy.lib.scheduler.security.resolver` doit aussi devenir `scheduler.security.resolver` pour cohérence.

### 2. `fsdeploy/__main__.py` (le NOUVEAU, argparse)

**Option A (recommandée)** : SUPPRIMER ce fichier. Il bypass daemon, n'a pas de SecurityResolver, pas de bus, pas d'intent registration. C'est une copie dégradée de ce que `fsdeploy/fsdeploy/__main__.py` fait déjà via `FsDeployDaemon`.

**Option B** : Le réécrire pour simplement déléguer à `fsdeploy/fsdeploy/__main__.py` :
```python
#!/usr/bin/env python3
"""Redirecteur vers le vrai entry point."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "fsdeploy"))
from fsdeploy.__main__ import app
if __name__ == "__main__":
    app()
```

**Option C** : Le garder mais le faire passer par `FsDeployDaemon` comme le typer :
```python
from fsdeploy.lib.daemon import FsDeployDaemon
daemon = FsDeployDaemon(config=cfg)
daemon.run(mode="tui")
```

**Le worker doit choisir Option A ou B.** L'Option C nécessite de recâbler tous les args argparse → config daemon, c'est trop pour cette tâche.

### 3. `pyproject.toml`

**Fix** : l'entry point doit pointer vers le vrai point d'entrée. Si on supprime le nouveau `__main__.py` (Option A) :
```toml
[project.scripts]
fsdeploy = "fsdeploy.__main__:app"
```

Ou si le package est structuré `fsdeploy/fsdeploy/` :
```toml
[project.scripts]
fsdeploy = "fsdeploy.fsdeploy.__main__:app"
```

**Note** : le `[tool.hatch.build.targets.wheel] packages = ["lib"]` est aussi faux — doit être `["fsdeploy"]` pour que le package soit installable.

### 4. `fsdeploy/lib/ui/bridge.py`

**Vérifier** que le triple fallback a été nettoyé. Si le code fait encore :
```python
if self._global_bridge is None:
    self._global_bridge = GlobalBridge(runtime=..., store=...)
```
→ remplacer par :
```python
if self._global_bridge is None:
    from log import get_logger
    log = get_logger("ui.bridge")
    log.error("scheduler_bridge_unavailable")
    # DummyBridge loggué
    class LoggedDummyBridge:
        def emit(self, event_name, *a, **kw):
            log.warning("dummy_bridge_emit", event=event_name)
            return "dummy-ticket"
        def poll(self): return []
        def __getattr__(self, name):
            return lambda *a, **kw: None
    self._global_bridge = LoggedDummyBridge()
```

---

## Critères d'acceptation

1. **Un seul entry point fonctionne** : `python3 -m fsdeploy --debug` démarre via `FsDeployDaemon`, loggue `scheduler_global_instance_set`, affiche la TUI.

2. **Import test** : `cd lib && python3 -c "from scheduler.core.scheduler import Scheduler; s = Scheduler.global_instance(); print(type(s.runtime))"` → `<class 'scheduler.core.runtime.Runtime'>` sans erreur.

3. **`cd lib && python3 test_run.py`** → 3/3 pass.

4. **`pip install -e .`** fonctionne depuis la racine du repo (si pyproject.toml est corrigé).

5. **Le nouveau `fsdeploy/__main__.py` (argparse)** est soit supprimé, soit redirige vers le daemon.

---

## Ne pas toucher

- Bus, logs, config → Phases 12-14
- Overlay → Phase 11
- Screens UI → Phase 10
- launch.sh → Phase 9
- Sécurité → Phase 17
- Câblage lib↔UI → Phase 16