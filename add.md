# add.md — Tâche 8.1b : Fix import path `scheduler.core.runtime`

> **Worker** : un seul fichier à modifier, un seul fix.

---

## Ce qui a été fait (tout OK ✅)

- `fsdeploy/__main__.py` → redirecteur vers typer ✅
- `pyproject.toml` → `fsdeploy.__main__:app` + `packages = ["fsdeploy"]` ✅
- `ui/bridge.py` → `LoggedDummyBridge` avec warning ✅

## Ce qui reste (1 fix)

### Fichier : `fsdeploy/lib/scheduler/core/scheduler.py`

Dans `global_instance()`, ligne :
```python
from fsdeploy.lib.scheduler.runtime import Runtime
```

**Le module `fsdeploy.lib.scheduler.runtime` est un répertoire** contenant `state.py` et `monitor.py`. Il n'exporte PAS `Runtime`. La classe `Runtime` (avec `event_queue`, `intent_queue`, `state`) est dans `fsdeploy.lib.scheduler.core.runtime`.

**Fix** — remplacer par :
```python
from fsdeploy.lib.scheduler.core.runtime import Runtime
```

**Contexte** : les trois autres imports dans la même méthode utilisent déjà le bon préfixe `fsdeploy.lib.scheduler.core.*` :
```python
from fsdeploy.lib.scheduler.core.resolver import Resolver      # ← .core. ✅
from fsdeploy.lib.scheduler.core.executor import Executor       # ← .core. ✅
from fsdeploy.lib.scheduler.runtime import Runtime              # ← manque .core. ❌
from fsdeploy.lib.scheduler.security.resolver import SecurityResolver  # ✅
```

**Note** : le daemon (`lib/daemon.py`) et les tests (`lib/test_run.py`) utilisent le style relatif `from scheduler.core.runtime import Runtime` (car `lib/` est dans sys.path). Les deux styles fonctionnent tant qu'ils sont cohérents. Le style absolute `fsdeploy.lib.scheduler.core.*` est celui choisi dans `global_instance()` — il faut juste ajouter le `.core.` manquant.

---

## Critère d'acceptation

```bash
cd fsdeploy/lib && python3 -c "
from scheduler.core.scheduler import Scheduler
s = Scheduler.global_instance()
print(type(s.runtime))
print(type(s.runtime.event_queue))
print('OK')
"
```

Doit afficher :
```
<class 'scheduler.core.runtime.Runtime'>
<class 'scheduler.queue.event_queue.EventQueue'>
OK
```

Et toujours :
```bash
cd fsdeploy/lib && python3 test_run.py
```
→ 3/3 pass.

---

## Après 8.1b — quelle tâche suivante ?

Une fois 8.1b ✅, le scheduler↔bridge est unifié. Les tâches P0 restantes par ordre d'impact :

1. **16.20 + 16.21** (créer intents `mount.request` et `pool.import`) — sans ça MountsScreen et DetectionScreen crashent dès qu'on clique un bouton
2. **10.1** (escape Unicode detection.py) — affichage cassé
3. **16.50** (doublon `config.snapshot.*`) — intent écrasé silencieusement
4. **10.5** (supprimer doublons écrans) — confusion graph/security/multiarch
