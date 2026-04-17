# add.md — 16.53 + 10.4

Deux correctifs simples. L'un est une suppression de 5 lignes, l'autre un déplacement d'imports.

---

## Fix 1 — 16.53 : Supprimer `init.detect` doublon de `system_intent.py`

**Fichier** : `fsdeploy/lib/intents/system_intent.py`

**Problème** : `@register_intent("init.detect")` et sa classe `InitDetectIntent` sont définis dans ce fichier. Mais le même intent est déjà défini dans `init_intent.py` (le fichier dédié aux intents `init.*`). Le dernier importé écrase l'autre silencieusement.

**Ce qu'il faut** : supprimer la classe `InitDetectIntent` et son décorateur `@register_intent("init.detect")` de `system_intent.py`. Ne toucher à rien d'autre dans ce fichier. L'intent reste dans `init_intent.py`.

---

## Fix 2 — 10.4 : `welcome.py` — rendre les imports d'écrans lazy

**Fichier** : `fsdeploy/lib/ui/screens/welcome.py`

**Problème** : en haut du fichier, 4 imports top-level :
```
from .security import SecurityScreen
from .graph import GraphScreen
from .intentlog import IntentLogScreen
from .metrics import MetricsScreen
```

Si un seul de ces fichiers a un import cassé, welcome.py ne charge pas et la TUI ne démarre plus du tout.

**Ce qu'il faut** : déplacer ces 4 imports dans la méthode `_switch_to_screen` qui les utilise, avec un try/except par écran. Le `screen_map` dans cette méthode doit construire ses valeurs au moment de l'appel, pas au chargement du module. L'app utilise déjà des imports lazy dans `app.py screen_map` — même principe ici.

---

## Critères d'acceptation

1. `grep -c "init.detect" fsdeploy/lib/intents/system_intent.py` → `0`
2. `grep -c "init.detect" fsdeploy/lib/intents/init_intent.py` → `1` ou plus
3. `python3 -c "from fsdeploy.lib.ui.screens.welcome import WelcomeScreen; print('OK')"` → `OK` même si `graph.py` est temporairement cassé
4. `cd fsdeploy/lib && python3 test_run.py` → 3/3 pass
