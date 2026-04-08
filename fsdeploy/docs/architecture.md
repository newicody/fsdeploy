# Architecture de fsdeploy

Fsdeploy est un outil de gestion de déploiement de systèmes de fichiers ZFS, conçu pour être extensible, robuste et interopérable avec différents systèmes d'initialisation.

## Vue d'ensemble

L'application est organisée en plusieurs couches découplées :

1. **Interface utilisateur (UI)** – une interface textuelle (TUI) construite avec Textual.
2. **Bridge UI‑scheduler** – pont qui permet à l'UI d'émettre des événements sans connaître les détails du scheduler.
3. **Scheduler** – moteur d'orchestration des intents, des tâches et des ressources.
4. **Bus d'événements** – système de communication asynchrone entre les composants.
5. **Couche sécurité** – vérification des permissions pour chaque opération.
6. **Journalisation compressée (intentlog)** – stockage persistant et compressé des événements.
7. **Modules fonctionnels** – implémentations concrètes des tâches (détection, montage, snapshot, intégration init, etc.)

## Diagramme des flux

```
┌─────────────────┐    événements    ┌──────────────────┐
│      UI         ├─────────────────►│   SchedulerBridge│
│   (Textual)     │                  │                  │
└─────────────────┘                  └──────────┬───────┘
                                                │ tickets
                                                ▼
┌─────────────────┐    intents       ┌──────────────────┐
│   EventQueue    ├─────────────────►│   IntentQueue    │
└─────────────────┘                  └──────────┬───────┘
                                                │
                                                ▼
┌─────────────────┐       tasks      ┌──────────────────┐
│   TaskQueue     │◄─────────────────┤   Resolver       │
└────────┬────────┘                  └──────────────────┘
         │
         ▼
┌─────────────────┐       locks      ┌──────────────────┐
│   Workers       ├─────────────────►│   RuntimeState   │
└─────────────────┘                  └──────────────────┘
         │
         ▼
┌─────────────────┐    résultats     ┌──────────────────┐
│   Exécution     ├─────────────────►│   RecordStore    │
│   (sous‑process)│                  │   (Huffman)      │
└─────────────────┘                  └──────────────────┘
```

## Détail des composants

### SchedulerBridge

Le pont expose deux méthodes principales :

- `submit_event(event_name, **params)` – émet un événement prioritaire.
- `submit(intent)` – soumet un intent directement.

Chaque appel crée un ticket (objet `Ticket`) qui peut être interrogé pour connaître le statut de l'opération (`pending`, `completed`, `failed`). Les tickets sont mis à jour automatiquement lors des appels à `poll()`.

### Scheduler

Le scheduler maintient deux files thread‑safe :

- **EventQueue** – événements en attente de traitement (priorité négative traitée en premier).
- **IntentQueue** – intents produits par les handlers d'événements.

Le scheduler extrait périodiquement les événements, les convertit en intents via des handlers enregistrés (`register_intent`), puis résout chaque intent en une liste de tâches (`Task`). Les tâches sont ensuite exécutées par un pool de workers, avec acquisition de verrous sur les ressources (`Resource`) et vérification de sécurité.

### RuntimeState

Gère l'état d'exécution global :

- Compteurs de parallélisme et limites.
- Verrous acquis (`Lock`).
- Historique des tâches terminées (`completed`, `failed`).
- Informations de réessai (`retry`).

### Bus d'événements (`MessageBus`)

Singleton global permettant l'émission et la souscription à des événements nommés. Utilisé pour notifier les composants de changements d'état sans couplage direct.

### Couche sécurité

Arbre hiérarchique de permissions (`SecurityNode`). Chaque tâche peut être décorée avec des décorateurs de sécurité (`@security.dataset.mount`, `@security.dataset.destroy`, etc.) qui vérifient, au moment de la résolution, que l'utilisateur/processus a le droit d'effectuer l'action sur la ressource cible.

### Intentlog

Système de stockage append‑only compressé avec un codec Huffman adaptatif. Les enregistrements (`Record`) sont indexés par catégorie, sévérité, préfixe de chemin et plage temporelle, permettant des requêtes efficaces pour l'affichage de l'historique.

## Exemple de flux complet

1. L'utilisateur clique sur le bouton « Détecter les pools » dans l'UI.
2. L'UI appelle `bridge.emit("detection.start", pools=["boot_pool"])`.
3. Le `SchedulerBridge` crée un ticket et place un `BridgeEvent` dans l'`EventQueue`.
4. Un handler enregistré (`register_bridge_event_handler`) convertit l'événement en `DetectionIntent`.
5. L'intent est poussé dans l'`IntentQueue`.
6. Le scheduler récupère l'intent et appelle sa méthode `build_tasks()`, qui retourne une `DetectionTask`.
7. La tâche est placée dans la `TaskQueue`, après vérification des verrous (aucun autre accès concurrent aux pools) et des permissions (l'utilisateur peut lire les informations ZFS).
8. Un worker disponible exécute la tâche, qui lance `zpool list` et parse la sortie.
9. Le résultat est enregistré dans `RuntimeState.completed` et le ticket correspondant est marqué comme `completed`.
10. L'UI, via `poll()`, détecte que le ticket est terminé et met à jour l'affichage avec la liste des pools.

---

*Document généré le 2026‑04‑08. Mise à jour automatique via le script `contrib/generate_doc.py`.*
