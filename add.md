# add.md — 24.1 : Correction Architecture UI & Migration Screens

## 1. Noyau : `fsdeploy/ui/bridge.py`
**Actions :**
- Modifier `__init__(self, runtime=None, store=None)` pour accepter les arguments de `app.py`.
- Ajouter `emit(self, event_name, callback=None, priority=None, **params)` :
  - Génère un ticket via `submit_event`.
  - Enregistre le callback si fourni via `on_result`.
- Corriger `_log_ticket` : Envoyer un seul dictionnaire `data` au bus au lieu de paramètres nommés.

## 2. Point d'entrée : `fsdeploy/ui/app.py`
**Actions :**
- Modifier l'instanciation : `self.bridge = SchedulerBridge(runtime=self.runtime, store=self.store)`.

## 3. Patch Global : `fsdeploy/lib/ui/screens/`
**Actions :** Pour chaque fichier ci-dessous, s'assurer que :
1. `from fsdeploy.ui.bridge import SchedulerBridge` est présent.
2. `self.bridge = SchedulerBridge.default()` est appelé dans `on_mount`.
3. Tous les anciens appels `messagebus.emit` ou `scheduler.submit` sont remplacés par `self.bridge.emit()`.

**Fichiers à modifier :**
- **Stockage/ZFS :** `detection.py`, `pool_list.py`, `dataset_list.py`, `snapshot_manager.py`, `mount_explorer.py`, `scrub_monitor.py`, `quota_manager.py`, `replication_view.py`.
- **Système :** `disk_view.py`, `network_conf.py`, `service_status.py`, `update_manager.py`.
- **Monitoring :** `graph_view.py`, `log_streamer.py`, `task_monitor.py`, `dashboard.py`.
- **Pilotage :** `pilot_main.py`, `config_editor.py`, `security_audit.py`, `user_access.py`, `shell_access.py`, `vms_containers.py`, `help_screen.py`.

## Critères de Succès
- Démarrage sans `TypeError`.
- `grep -r "bridge.emit" fsdeploy/lib/ui/screens/` renvoie des résultats pour chaque écran.
