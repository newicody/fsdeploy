# add.md — 24.1 : Fix Architecture UI (Bridge & Screens)

## Problème
Le `SchedulerBridge` empêche le démarrage (init mismatch) et ne fournit pas la méthode `emit` attendue par les écrans.

## Modifications Techniques

### 1. `fsdeploy/ui/bridge.py`
- **Init** : Modifier `__init__(self, runtime=None, store=None)` pour stocker les références.
- **Alias `emit`** : Ajouter la méthode `emit(self, event_name, callback=None, priority=None, **params)` :
    - Doit appeler `submit_event`.
    - Doit enregistrer le callback via `on_result` si présent.
- **Fix Signature** : Dans `_log_ticket`, regrouper les infos dans un dict `data` avant l'émission au bus.

### 2. `fsdeploy/ui/app.py`
- S'assurer que l'instanciation est : `self.bridge = SchedulerBridge(runtime=self.runtime, store=self.store)`.

## Patch Global des 23 Écrans (`fsdeploy/lib/ui/screens/*.py`)
Pour chaque fichier d'écran :
1. Importer `SchedulerBridge`.
2. Faire `self.bridge = SchedulerBridge.default()` dans `on_mount`.
3. Remplacer les appels `bus.emit` ou `scheduler.submit` par `self.bridge.emit(...)`.

**Fichiers cibles :** `detection.py`, `pool_list.py`, `dataset_list.py`, `snapshot_manager.py`, `disk_view.py`, `network_conf.py`, `service_status.py`, `graph_view.py`, `log_streamer.py`, `task_monitor.py`, `dashboard.py`, `pilot_main.py`, `config_editor.py`, `security_audit.py`, `user_access.py`, `shell_access.py`, `vms_containers.py`, etc.
