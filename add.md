# add.md — 24.1 : Fix Architecture UI

> **STRICT DIRECTIVE** : Les fichiers ont été pushés. Utilise `/add` pour charger les chemins réels dans `fsdeploy/lib/ui/`.

## 📂 Fichiers cibles
- `fsdeploy/lib/ui/bridge.py`
- `fsdeploy/lib/ui/app.py`
- `fsdeploy/lib/ui/screens/*.py`

## 🛠 1. Correction : `fsdeploy/lib/ui/bridge.py`
- **Import** : Ajouter `import uuid`.
- **Constructeur** : `def __init__(self, runtime=None, store=None):`. Stocker les références dans `self._scheduler` et `self._store`.
- **Interface** : Injecter la méthode `emit` :
    ```python
    def emit(self, event_name, callback=None, priority=None, **params):
        ticket_id = str(uuid.uuid4())
        self.submit_event(event_name, priority=priority, **params)
        if callback:
            self.on_result(ticket_id, callback)
        return ticket_id
    ```

## 📱 2. Correction : `fsdeploy/lib/ui/app.py`
- Modifier l'instanciation : `self.bridge = SchedulerBridge(runtime=self.runtime, store=self.store)`.

## 📺 3. Migration Screens : `fsdeploy/lib/ui/screens/`
- Remplacer systématiquement `self.app.bus.emit` par `self.bridge.emit`.
- Vérifier `self.bridge = SchedulerBridge.default()` dans chaque `on_mount`.
