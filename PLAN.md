# PLAN.md — fsdeploy (branche `dev`)

> **Dernière mise à jour** : 2026-04-19
> **Itération worker** : 87
> **Codebase** : ~24 300 lignes Python, 71 intents, 23 écrans, 19 tests
> **Tâche active** : **22.2** — voir `add.md`

---

## ✅ Terminé

| ID | Description |
|----|-------------|
| 18.1 | Tests SecurityResolver + Isolation (test_security_resolver.py, 19 tests) |
| 11.1-2 | SquashFS/overlay tasks + intents + UI mounts |
| 23.1-2 | Isolation : isolation.py + cgroups executor |
| 22.1 | Fix __main__.py (fsdeploy.fsdeploy supprimé) |
| 19.2 | 23 écrans câblés |
| 17.1 | SecurityResolver 4 niveaux + executor |
| 20.1-3, 21.1, 10.5, 9.1, 8.1, 16.x, 17.7, 7.0, Phase 1-6 | Tout le reste |

---

## 🚧 Tâche active — 22.2

Voir `add.md`.

---

## ⏳ Restant

### P0 — CLI cassée

| ID | Description |
|----|-------------|
| **22.2** | Fix sys.path dans __main__.py + __init__.py (régression 20.1) |

### P1

| ID | Description |
|----|-------------|
| **23.3** | Mount namespace pour DatasetProbeTask |
| **18.2** | Tests overlay + intent pipeline |

### P2

| ID | Description |
|----|-------------|
| **18.3** | Tests TUI Pilot |

---

## Bugs CLI — Diagnostic

### Bug 1 : `__main__.py` sys.path incorrect

```python
# ACTUEL (cassé) :
sys.path.insert(0, os.path.dirname(__file__))  # = fsdeploy/
from fsdeploy.cli import app  # cherche fsdeploy/fsdeploy/cli.py → FAIL

# CORRECT :
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))  # = parent de fsdeploy/
from fsdeploy.cli import app  # cherche fsdeploy/cli.py → OK
```

### Bug 2 : `__init__.py` ne setup plus lib/ dans sys.path

La suppression de `fsdeploy/fsdeploy/__init__.py` (20.1) a perdu ce code :
```python
_LIB_DIR = _PACKAGE_DIR / "lib"
sys.path.insert(0, str(_LIB_DIR))
```

Beaucoup de fichiers dans `lib/` utilisent des imports bare :
- `from scheduler.model.task import Task`
- `from scheduler.security.decorator import security`
- `from scheduler.model.resource import Resource`

Sans `lib/` dans sys.path, ces imports cassent.