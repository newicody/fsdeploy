# add.md — 24.1 : Refonte Bridge & Migration des 23 Écrans

## Problème
Le `SchedulerBridge` actuel possède un constructeur `__init__()` sans arguments, alors que `app.py` lui en transmet deux. La méthode `_log_ticket` provoque un `TypeError` avec le `MessageBus`. Enfin, les écrans appellent `bridge.emit()`, méthode inexistante dans la classe actuelle.

## Modifications prioritaires

### 1. `fsdeploy/ui/bridge.py`
- **Initialisation** : Modifier `__init__(self, runtime=None, store=None)` pour stocker les références.
- **Méthode `emit`** : Ajouter `emit(self, event_name, callback=None, priority=None, **params)` qui appelle `submit_event` et gère le callback.
- **Logique de Log** : Dans `_log_ticket`, regrouper les données dans un dictionnaire `data` unique avant d'appeler `self._event_bus.emit` pour éviter les erreurs de signature.
- **Auto-nettoyage** : Appeler `self.cleanup_old()` à la fin de `poll()` pour éviter la saturation de `_tickets`.

### 2. `fsdeploy/ui/app.py`
- Mettre à jour l'instanciation : `self.bridge = SchedulerBridge(runtime=self.runtime, store=self.store)`.

## Patch Global des Écrans (`fsdeploy/lib/ui/screens/`)

Chaque écran listé doit être modifié pour utiliser `SchedulerBridge.default()` et la nouvelle méthode `emit()`.

### Liste exhaustive des fichiers à traiter :
- **ZFS & Stockage** : `detection.py`, `pool_list.py`, `dataset_list.py`, `snapshot_manager.py`, `mount_explorer.py`, `scrub_monitor.py`, `quota_manager.py`, `replication_view.py`.
- **Système & Réseau** : `disk_view.py`, `network_conf.py`, `service_status.py`, `update_manager.py`.
- **Monitoring & Logs** : `graph_view.py`, `log_streamer.py`, `task_monitor.py`, `dashboard.py`.
- **Pilotage & Sécurité** : `pilot_main.py`, `config_editor.py`, `security_audit.py`, `user_access.py`, `shell_access.py`, `vms_containers.py`, `help_screen.py`.

### Logique d'injection (Standard) :
```python
def on_mount(self):
    self.bridge = SchedulerBridge.default()
    # Remplacer les anciens appels bus par :
    self.bridge.emit("ui.screen.active", screen=self.__class__.__name__)
