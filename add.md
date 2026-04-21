# add.md — 24.1 : Fix Architecture UI

> **CONSIGNE** : Les fichiers `bridge.py` et `app.py` sont déjà chargés via la config. 
> Ta mission est de modifier ces deux fichiers et de patcher les écrans dans `fsdeploy/lib/ui/screens/`.

## 🛠 1. Dans `fsdeploy/lib/ui/bridge.py`
- Ajouter `import uuid`.
- Modifier le constructeur : `def __init__(self, runtime=None, store=None):`.
- Ajouter la méthode `emit(self, event_name, callback=None, priority=None, **params)`.

## 📱 2. Dans `fsdeploy/lib/ui/app.py`
- S'assurer que l'instanciation est : `self.bridge = SchedulerBridge(runtime=self.runtime, store=self.store)`.

## 📺 3. Dans `fsdeploy/lib/ui/screens/*.py`
- Remplacer tous les `self.app.bus.emit` par `self.bridge.emit`.
- Vérifier `self.bridge = SchedulerBridge.default()` dans `on_mount`.
