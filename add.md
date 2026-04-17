# add.md — 10.5 + 10.2

---

## Fix 1 — 10.5 : Supprimer les doublons d'écrans

**Fichiers** dans `fsdeploy/lib/ui/screens/` :

Il y a des paires quasi-identiques :
- `graph.py` (GraphScreen) ET `graph_enhanced.py` (GraphEnhancedScreen)
- `security.py` (SecurityScreen) ET `security_enhanced.py` (SecurityEnhancedScreen)
- `multiarch.py` (MultiArchScreen) ET `multiarch_screen.py` (si existant)

Et `navigation.py` importe les versions `_enhanced` au top-level — même problème que welcome.py avait.

**Ce qu'il faut** :
- Pour chaque paire, garder un seul fichier. Garder celui qui utilise le bridge (`@property def bridge`) et qui n'est pas hardcodé. En général c'est la version simple (`graph.py`, `security.py`) car les `_enhanced` sont des prototypes avec animation qui ne sont connectés à rien.
- Supprimer `graph_enhanced.py` et `security_enhanced.py`.
- Supprimer `navigation.py` — c'est du code mort qui importe les fichiers supprimés et qui n'est enregistré nulle part dans `screen_map` de `app.py`.
- Si `multiarch_screen.py` existe en doublon de `multiarch.py`, supprimer l'un des deux.
- Mettre à jour `app.py screen_map` si nécessaire (normalement déjà correct car il pointe vers les versions simples).

---

## Fix 2 — 10.2 : Uniformiser les imports dans les écrans

**Fichiers** : tous les fichiers dans `fsdeploy/lib/ui/screens/*.py`

**Problème** : trois styles d'import coexistent :
- `from fsdeploy.lib.ui.screens.X import Y` (absolu complet)
- `from .X import Y` (relatif)
- `from ui.screens.X import Y` (dépend de sys.path)

Le troisième style casse si `lib/` n'est pas dans sys.path. Les deux premiers fonctionnent.

**Ce qu'il faut** : dans les fichiers `screens/*.py`, le style relatif `from .X import Y` est le plus robuste (fonctionne quel que soit le sys.path). Dans `app.py`, le style `importlib.import_module("fsdeploy.lib.ui.screens.X")` est déjà utilisé et correct. Uniformiser les écrans restants qui utilisent le style absolu avec chemin complet de `fsdeploy.lib.ui.screens`.

Note : ne pas toucher aux imports des modules `scheduler.*`, `function.*`, `bus.*` — ceux-là dépendent de `lib/` dans sys.path et c'est voulu.

---

## Critères d'acceptation

1. `ls fsdeploy/lib/ui/screens/graph_enhanced.py fsdeploy/lib/ui/screens/security_enhanced.py fsdeploy/lib/ui/screens/navigation.py 2>/dev/null` → aucun fichier trouvé
2. `grep -r "graph_enhanced\|security_enhanced\|NavigationScreen" fsdeploy/lib/ui/screens/*.py` → aucun résultat
3. `cd fsdeploy/lib && python3 test_run.py` → 3/3 pass
4. `python3 -c "from fsdeploy.lib.ui.app import FsDeployApp; print('OK')"` → OK
