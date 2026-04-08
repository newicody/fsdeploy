# Documentation des APIs internes de fsdeploy

Cette documentation décrit les principaux modules internes de fsdeploy, leurs responsabilités et leur utilisation.

## Module `bus`

Le bus d'événements permet une communication découplée entre les composants.

### Classes principales

- **`EventSource`** : classe de base pour les sources d'événements.
- **`MessageBus`** : bus global singleton qui permet d'émettre et de souscrire à des événements.

### Utilisation typique

```python
from fsdeploy.lib.bus.event_bus import MessageBus

bus = MessageBus.global_instance()
bus.emit("mon.evenement", donnees={"valeur": 42})
```

Les événements émis sur le bus peuvent être captés par des handlers enregistrés (intents, tâches).

## Module `scheduler`

Le scheduler orchestre l'exécution des intents, des tâches et gère les ressources.

### Composants principaux

- **`Intent`** : représente une intention d'exécution, produite par un événement.
- **`Task`** : unité d'exécution concrète (exécutée par un worker).
- **`RuntimeState`** : état d'exécution global (locks, parallélisme, retry).
- **`Scheduler`** : cœur du scheduler, contient les files d'intents et d'événements.
- **`SchedulerBridge`** : pont entre l'UI (ou tout client) et le scheduler.

### Flux typique

1. Un événement est émis (ex: `BridgeEvent`).
2. Les handlers d'événements produisent des intents (`Intent`).
3. Les intents sont résolus en listes de tâches (`build_tasks()`).
4. Les tâches sont placées dans la file de tâches, avec acquisition de locks et vérification de sécurité.
5. Les tâches sont exécutées par des workers parallèles.
6. Les résultats sont collectés dans `RuntimeState` et les tickets sont mis à jour.

### Bridge UI‑scheduler

Le `SchedulerBridge` offre une API simple pour soumettre des événements et des intents, et suivre leur achèvement via des tickets. Il délègue au scheduler global et permet des fallbacks via le bus d'événements.

## Module `security`

La couche sécurité garantit que seules les opérations autorisées sont exécutées, en fonction de la configuration et du contexte.

### Composants principaux

- **`SecurityNode`** : nœud dans l'arbre de sécurité (ressource, action, permission).
- **`SecurityResolver`** : résout les permissions pour une tâche donnée.
- Décorateurs de sécurité : `@security.dataset.mount`, `@security.dataset.destroy`, etc., qui vérifient les permissions avant l'exécution.

### Intégration avec le scheduler

Chaque tâche peut être annotée avec des décorateurs de sécurité. Lors de la résolution, le `SecurityResolver` est consulté pour déterminer si l'utilisateur/processus a le droit d'exécuter l'action sur la ressource cible.

## Module `intentlog`

Système de journalisation compressé et persistant.

### Composants

- **`HuffmanCodec`** : codec Huffman adaptatif pour compresser les tokens fréquents.
- **`RecordStore`** : stockage append‑only de records compressés.
- **`PersistentRecordStore`** : persistance des records dans un fichier JSONL.
- **`HuffmanStore`** : base unifiée combinant codec et plusieurs RecordStore.

Les logs sont compressés en temps réel, avec reconstruction périodique de l'arbre de Huffman. Ils peuvent être filtrés par catégorie, sévérité, préfixe et plage temporelle.

## Exemples d'utilisation

### Émission d'un événement depuis l'UI

```python
# Dans un écran Textual
ticket_id = self.app.bridge.emit(
    "detection.start",
    pools=["boot_pool"],
    callback=self._on_detection_finished,
    priority=-100,
)
```

### Création d'un intent personnalisé

```python
from fsdeploy.lib.scheduler.model.intent import Intent

class MonIntent(Intent):
    def build_tasks(self):
        from . import MaTache
        return [MaTache(id="ma_tache", params=self.params)]
```

### Enregistrement d'un handler d'événement bridge

```python
from fsdeploy.lib.scheduler.model.event import register_bridge_event_handler

def mon_handler(event):
    # Convertir l'événement en intents
    return [MonIntent(params=event.params)]

register_bridge_event_handler("detection.start", mon_handler)
```

---

Cette documentation sera enrichie au fur et à mesure de l'évolution du code.
