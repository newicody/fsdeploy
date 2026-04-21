# add.md — 24.1 : Fix Architecture UI (Bridge & Screens)

> **ACTION REQUISE** : Pour appliquer cette mise à jour, tu DOIS modifier les fichiers suivants. S'ils ne sont pas dans ton contexte, ajoute-les maintenant.

## 📂 Fichiers à modifier :
- `fsdeploy/ui/bridge.py`
- `fsdeploy/ui/app.py`
- `fsdeploy/lib/ui/screens/*.py` (les 23 écrans)

## 🛠 1. Correction du Noyau : `fsdeploy/ui/bridge.py`
- **Imports** : Ajouter `import uuid`.
- **Constructeur** : Modifier en `def __init__(self, runtime=None, store=None):`. Stocker les références dans `self._scheduler` et `self._store`.
- **Méthode `emit`** : Ajouter cette interface universelle :
    ```python
    def emit(self, event_name, callback=None, priority=None, **params):
        ticket_id = str(uuid.uuid4())
        self.submit_event(event_name, priority=priority, **params)
        if callback:
            self.on_result(ticket_id, callback)
        return ticket_id
    ```
- **Fix Log** : Dans `_log_ticket`, envoyer un dictionnaire `data` unique au bus au lieu d'arguments nommés.

## 📱 2. Correction Application : `fsdeploy/ui/app.py`
- S'assurer que le Bridge est instancié avec : `self.bridge = SchedulerBridge(runtime=self.runtime, store=self.store)`.

## 📺 3. Migration des 23 Écrans
Pour chaque fichier dans `fsdeploy/lib/ui/screens/` :
- S'assurer que `self.bridge = SchedulerBridge.default()` est dans `on_mount`.
- Remplacer tous les `self.app.bus.emit(...)` par `self.bridge.emit(...)`.

## Critères de Validation
- Aucun crash `TypeError` au démarrage.
- Tous les écrans utilisent l'ID de ticket via `uuid` pour le suivi
