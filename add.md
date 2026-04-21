# add.md — 24.1.b : Migration des appels de bus

## 🛠 Action Prioritaire
Dans TOUS les fichiers de `fsdeploy/lib/ui/screens/*.py` :
1. Identifier les appels à `self.app.bus.emit(event, ...)`
2. Les remplacer par `self.bridge.emit(event, ...)`
3. **Vérifier** : Si un écran n'a pas encore `self.bridge = SchedulerBridge.default()` dans `on_mount`, l'ajouter.
