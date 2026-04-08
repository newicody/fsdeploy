# Bridge UI‑Scheduler

Le pont entre l'interface utilisateur (UI) et le scheduler permet aux écrans d’émettre des intents et de recevoir les résultats en temps réel. Cette documentation explique comment utiliser le `SchedulerBridge` et le `MessageBus` pour interagir avec le cœur d'exécution de fsdeploy.

## Architecture du pont

Le scheduler expose un point d'entrée unique (`SchedulerBridge`) qui permet de soumettre des intents. Ces intents sont ensuite placés dans la file `IntentQueue` et traités par le `Scheduler`. Les résultats et les événements intermédiaires sont diffusés via un bus d'événements global (`MessageBus`). L'UI peut s'abonner à ces événements pour mettre à jour l'affichage en temps réel.

## Obtenir le bridge

Dans un écran Textual, le bridge est généralement accessible via l'attribut `app.bridge` (si l'application a défini cet attribut). Sinon, vous pouvez utiliser la méthode de classe `SchedulerBridge.default()`.

```python
from fsdeploy.lib.scheduler.bridge import SchedulerBridge

bridge = SchedulerBridge.default()
```

Dans les écrans fournis (comme `GraphViewScreen`), une propriété `bridge` est déjà définie pour faciliter l'accès.

## Émettre un intent

Pour émettre un intent, il faut d'abord instancier une sous‑classe d'`Intent` avec les paramètres appropriés, puis appeler `bridge.submit(intent)`.

```python
from fsdeploy.lib.scheduler.model.intent import Intent
from fsdeploy.lib.scheduler.bridge import SchedulerBridge

class MonIntent(Intent):
    def build_tasks(self):
        # retourner la liste des tâches
        ...

bridge = SchedulerBridge.default()
intent = MonIntent(id="mon_intent", params={"cle": "valeur"})
future = bridge.submit(intent)
```

La méthode `submit` retourne un objet `concurrent.futures.Future` qui vous permet d'attendre le résultat final de l'intent (via `future.result(timeout)`), ou de vérifier son état.

## Événements du bus

Pendant l'exécution de l'intent, le scheduler émet plusieurs types d'événements sur le `MessageBus` global. Les écrans peuvent s'y abonner pour réagir à l'avancement.

Événements principaux :

- `task.started`   : une tâche a commencé.
- `task.progress`  : mise à jour de progression (si la tâche en fournit).
- `task.finished`  : une tâche s'est terminée (avec succès ou échec).
- `task.failed`    : une tâche a échoué (déclenché en plus de `task.finished`).
- `intent.resolved`: l'intent a été complètement résolu.

Exemple d'abonnement :

```python
from fsdeploy.lib.bus.event_bus import MessageBus

bus = MessageBus.global_instance()

def on_task_finished(event):
    task_id = event.data["task_id"]
    result  = event.data.get("result")
    self.notify(f"Tâche {task_id} terminée")

bus.subscribe("task.finished", on_task_finished)
```

Chaque événement transporte un dictionnaire `data` contenant les détails pertinents (identifiants, résultats, erreurs éventuelles).

## Intégration avec un écran Textual

Dans un écran Textual, il est recommandé de s'abonner aux événements dans `on_mount` et de se désabonner dans `on_unmount` pour éviter des références circulaires.

```python
class MonEcran(Screen):
    def on_mount(self):
        self.bus = MessageBus.global_instance()
        self.bus.subscribe("task.finished", self._on_task_finished)

    def on_unmount(self):
        self.bus.unsubscribe("task.finished", self._on_task_finished)

    def _on_task_finished(self, event):
        # Mettre à jour l'UI (rappelé depuis le thread du bus)
        self.call_from_thread(self.update_display, event.data)
```

Le bus exécute les callbacks dans son propre thread ; utilisez `self.call_from_thread` (méthode de `Screen`) pour mettre à jour les widgets Textual en toute sécurité.

## Exemple complet : lancer une vérification de cohérence depuis l'UI

L'écran `GraphViewScreen` (voir `fsdeploy/lib/ui/screens/graph.py`) illustre l'utilisation du bridge pour récupérer l'état courant du scheduler (`bridge.get_scheduler_state()`). Voici comment on pourrait y ajouter l'émission d'un intent de vérification de cohérence :

```python
def action_run_coherence_check(self):
    from fsdeploy.lib.intents.system_intent import CoherenceCheckIntent
    intent = CoherenceCheckIntent(id="coherence_ui", params={})
    future = self.bridge.submit(intent)
    # vous pouvez choisir d'attendre de manière asynchrone
    # ou simplement laisser l'intent s'exécuter en arrière‑plan.
```

## Dépannage

- **`SchedulerBridge.default()` lève une exception** : assurez‑vous que le scheduler a été démarré avant d'utiliser le bridge (normalement pris en charge par l'application principale).
- **Les événements ne sont pas reçus** : vérifiez que vous vous êtes bien abonné avant le début de l'exécution de l'intent. Le bus ne garde pas d'historique des événements déjà émis.
- **L'UI ne se met pas à jour** : pensez à appeler `self.call_from_thread` car les callbacks du bus sont exécutés hors du thread de l'interface.

## Références

- `fsdeploy/lib/scheduler/bridge.py` – implémentation du pont.
- `fsdeploy/lib/bus/event_bus.py` – bus d'événements global.
- `fsdeploy/lib/scheduler.model.intent.py` – base des intents.
- `fsdeploy/lib/ui/screens.graph.py` – exemple d'écran utilisant le bridge.
