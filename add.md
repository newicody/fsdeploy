# add.md — 20.3 : Fusionner docs bridge + supprimer tests/contrib

## A. Fusionner les 2 docs bridge en un seul

Deux fichiers documentent la même chose :
- `fsdeploy/docs/bridge-ui-scheduler.md` (114L) — version SchedulerBridge/MessageBus
- `fsdeploy/docs/bridge_ui_scheduler.md` (106L) — version UIEventBridge/UICallbackRegistry

**Action :** Garder `fsdeploy/docs/bridge_ui_scheduler.md` (underscore, conforme Python) et supprimer `fsdeploy/docs/bridge-ui-scheduler.md`.

Avant de supprimer, vérifier si du contenu unique de `bridge-ui-scheduler.md` manque dans `bridge_ui_scheduler.md`. Si oui, ajouter les sections manquantes à `bridge_ui_scheduler.md` avant suppression.

Sections à vérifier :
- Exemple `bridge.submit(intent)` → `future.result(timeout)`
- Événements bus : `task.started`, `task.progress`, `task.finished`, `task.failed`, `intent.resolved`
- Exemple `bus.subscribe("task.finished", callback)`
- Intégration avec écran Textual (on_mount/on_unmount subscribe/unsubscribe)

```bash
git rm fsdeploy/docs/bridge-ui-scheduler.md
```

## B. Supprimer `tests/contrib/` (duplique `fsdeploy/contrib/`)

Le dossier `tests/contrib/` contient 6 fichiers qui dupliquent `fsdeploy/contrib/` :

```bash
git rm -r tests/contrib/
```

Vérifier qu'aucun test n'importe depuis `tests/contrib/` :
```bash
grep -r "tests/contrib\|tests\.contrib" --include="*.py" .
```

## Critères

1. `fsdeploy/docs/bridge-ui-scheduler.md` n'existe plus
2. `fsdeploy/docs/bridge_ui_scheduler.md` existe et contient les sections des deux anciens fichiers
3. `tests/contrib/` n'existe plus
4. Aucune référence cassée vers les fichiers supprimés
