# add.md — 24.1 : Refonte Bridge & Migration des 23 Écrans

## Problème
Incohérence entre `app.py` et `bridge.py` et manque d'une interface d'émission standardisée (`emit`) pour les écrans.

## Modifications de l'Architecture

### 1. `fsdeploy/ui/bridge.py`
- **Init** : Modifier `__init__(self, runtime=None, store=None)` pour accepter les arguments de l'App.
- **Méthode `emit`** : Ajouter `emit(self, event_name, callback=None, priority=None, **params)` comme alias de `submit_event`.
- **Signature Log** : Fixer `_log_ticket` pour envoyer un dictionnaire unique au bus.

### 2. `fsdeploy/ui/app.py`
- **Instanciation** : Passer `self.runtime` et `self.store` au constructeur du Bridge.

## Migration des Écrans (`fsdeploy/lib/ui/screens/`)

Chaque fichier listé ci-dessous doit être modifié pour :
1. Importer `SchedulerBridge`.
2. Initialiser `self.bridge = SchedulerBridge.default()` dans `on_mount`.
3. Remplacer les appels directs au bus/scheduler par `self.bridge.emit(...)`.

### Liste des fichiers à traiter par `aider` :

* **Gestion Pools/ZFS** :
    * `detection.py` : Migrer le scan des pools vers `bridge.emit("zfs.detect")`.
    * `pool_list.py` : Utiliser le bridge pour rafraîchir la liste.
    * `dataset_list.py` : Migrer les requêtes de propriétés.
    * `snapshot_manager.py` : Remplacer les créations de snapshots par des tickets.
* **Système & Stockage** :
    * `disk_view.py` : Migrer l'inventaire SMART/Disques.
    * `network_conf.py` : Migrer les changements d'IP/Interfaces.
    * `service_status.py` : Utiliser le bridge pour start/stop les démons.
* **Vues Temps Réel** :
    * `graph_view.py` : Utiliser `bridge.get_scheduler_state()` pour les métriques.
    * `log_streamer.py` : S'abonner aux flux via le bridge.
    * `task_monitor.py` : Utiliser `bridge.pending_tickets` pour l'affichage.
* **Configuration & Pilotage** :
    * `pilot_main.py` : Centraliser les commandes de pilotage via `emit`.
    * `config_editor.py` : Sauvegarder via des intents émis par le bridge.
    * `security_audit.py` : Lancer l'audit via le scheduler bridge.
* **Autres écrans (Total 23)** :
    * `dashboard.py`, `help_screen.py`, `mount_explorer.py`, `scrub_monitor.py`, `update_manager.py`, `replication_view.py`, `quota_manager.py`, `user_access.py`, `shell_access.py`, `vms_containers.py`.

## Critères de Validation
- Aucun `TypeError` à l'init du Bridge.
- `grep -r "bridge.emit" fsdeploy/lib/ui/screens/` doit retourner des résultats pour chaque fichier.
- Le suivi des tâches fonctionne via `bridge.poll()`.
