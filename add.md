# add.md — 24.1 : Refonte Bridge & Migration des 23 Écrans

## Problème
Le `SchedulerBridge` actuel possède un constructeur `__init__()` sans arguments, causant un crash à l'init. La méthode `_log_ticket` provoque un `TypeError` sur le bus. Les écrans appellent `bridge.emit()`, méthode absente de la classe.

## Modifications de l'Infrastructure

### 1. `fsdeploy/ui/bridge.py`
- **Initialisation** : Modifier `__init__(self, runtime=None, store=None)` pour accepter les références envoyées par l'App.
- **Méthode `emit`** : Ajouter `emit(self, event_name, callback=None, priority=None, **params)` qui appelle `submit_event` et enregistre le callback.
- **Logique de Log** : Dans `_log_ticket`, regrouper les données dans un dictionnaire `data` unique pour éviter les erreurs de signature `ticket_id`.
- **Nettoyage** : Appeler `self.cleanup_old()` à la fin de `poll()` pour limiter la croissance de `_tickets`.

### 2. `fsdeploy/ui/app.py`
- Mettre à jour l'instanciation : `self.bridge = SchedulerBridge(runtime=self.runtime, store=self.store)`.

## Patch Global des Écrans (`fsdeploy/lib/ui/screens/`)

Chaque fichier doit être modifié pour importer `SchedulerBridge`, l'initialiser via `.default()` dans `on_mount`, et utiliser `bridge.emit()`.

### Liste des 23 écrans à traiter :

1. **ZFS & Stockage** :
   - `detection.py` (Scan initial)
   - `pool_list.py` (Liste des pools)
   - `dataset_list.py` (Hiérarchie ZFS)
   - `snapshot_manager.py` (Gestion snapshots)
   - `mount_explorer.py` (Points de montage)
   - `scrub_monitor.py` (État de santé)
   - `quota_manager.py` (Limites/Quotas)
   - `replication_view.py` (Transferts distants)

2. **Système & Réseau** :
   - `disk_view.py` (Infos SMART/Disques)
   - `network_conf.py` (Interfaces IP)
   - `service_status.py` (Démons système)
   - `update_manager.py` (Mises à jour logicielles)

3. **Monitoring & Logs** :
   - `graph_view.py` (Statistiques temps réel)
   - `log_streamer.py` (Flux de journaux)
   - `task_monitor.py` (Historique des tickets bridge)
   - `dashboard.py` (Vue d'ensemble)

4. **Pilotage & Sécurité** :
   - `pilot_main.py` (Centre de contrôle)
   - `config_editor.py` (Fichiers JSON/YAML)
   - `security_audit.py` (Rapports de vulnérabilité)
   - `user_access.py` (ACL et permissions)
   - `shell_access.py` (Console intégrée)
   - `vms_containers.py` (Gestion virtualisation)
   - `help_screen.py` (Aide contextuelle)

## Critères de Validation
- L'application démarre sans crash `TypeError`.
- Tous les écrans utilisent `bridge.emit` au lieu d'appels directs au bus.
- `bridge.poll()` met correctement à jour le statut des tickets dans l'UI.
