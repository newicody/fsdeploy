# add.md — 24.1 : Fix Architecture UI (Bridge & Screens)

## 1. Fichier : `fsdeploy/ui/bridge.py`
**Actions :**
- Modifier `__init__(self, runtime=None, store=None)` : stocker `self._scheduler = runtime` et `self._store = store`.
- Ajouter la méthode `emit(self, event_name, callback=None, priority=None, **params)` :
    - Elle doit générer un `ticket_id` via `uuid.uuid4()`.
    - Elle doit appeler `self.submit_event(event_name, priority=priority, **params)`.
    - Si un `callback` est fourni, l'enregistrer via `self.on_result(ticket_id, callback)`.
- Fix `_log_ticket` : Remplacer l'envoi d'arguments nommés par un dictionnaire unique `data` pour éviter le `TypeError`.

## 2. Fichier : `fsdeploy/ui/app.py`
**Actions :**
- Vérifier que l'instanciation est bien : `self.bridge = SchedulerBridge(runtime=self.runtime, store=self.store)`.

## 3. Patch des Écrans : `fsdeploy/lib/ui/screens/*.py`
**Actions :** Appliquer à TOUS les fichiers du répertoire (23 fichiers) :
1. Ajouter `from fsdeploy.ui.bridge import SchedulerBridge`.
2. Dans `on_mount`, ajouter `self.bridge = SchedulerBridge.default()`.
3. Remplacer tout appel direct à `self.app.bus.emit` ou `self.app.scheduler.submit` par `self.bridge.emit(...)`.

## Critères de Validation
1. L'application se lance sans `TypeError` au niveau du Bridge.
2. `grep -r "bridge.emit" fsdeploy/lib/ui/screens/` renvoie des résultats pour chaque écran.
3. Les logs du bus montrent des payloads sous forme de dictionnaires cohérents.
