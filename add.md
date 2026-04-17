# add.md — Fix cli.py + 10.4

---

## Fix 1 — `cli.py` import cassé (régression 16.53)

**Fichier** : `fsdeploy/cli.py`

**Problème** : le fichier fait `from fsdeploy.lib.intents.system_intent import InitDetectIntent`. Cette classe a été supprimée de `system_intent.py` (fix 16.53). L'import crashe.

**Ce qu'il faut** : remplacer par `from fsdeploy.lib.intents.init_intent import InitDetectIntent` (c'est là que la classe vit maintenant).

---

## Fix 2 — 10.4 : `welcome.py` imports lazy

**Fichier** : `fsdeploy/lib/ui/screens/welcome.py`

**Problème** : 4 imports top-level au début du fichier :
```
from .security import SecurityScreen
from .graph import GraphScreen
from .intentlog import IntentLogScreen
from .metrics import MetricsScreen
```

Si un seul de ces modules a un problème d'import, le welcome screen entier ne charge pas et la TUI ne démarre plus.

**Ce qu'il faut** : supprimer ces 4 imports du top-level. Dans la méthode `_switch_to_screen`, importer chaque écran localement au moment de l'appel, avec un try/except pour chacun. L'app fait déjà ça dans `app.py` avec `screen_map` + `importlib.import_module` — même approche ici.

---

## Critères d'acceptation

1. `python3 -c "from fsdeploy.cli import app; print('OK')"` → `OK` (plus d'ImportError)
2. `python3 -c "from fsdeploy.lib.ui.screens.welcome import WelcomeScreen; print('OK')"` → `OK` même si `metrics.py` est temporairement cassé
3. `cd fsdeploy/lib && python3 test_run.py` → 3/3 pass
