# add.md — 24.1 : Finalisation Bridge

## 🛠 ACTION 1 : Initialisation manquante
Pour tous les fichiers dans `fsdeploy/lib/ui/screens/` n'ayant pas encore `self.bridge` :
- Ajouter l'import : `from fsdeploy.lib.ui.bridge import SchedulerBridge`
- Ajouter dans `on_mount` : `self.bridge = SchedulerBridge.default()`

## 🛠 ACTION 2 : Migration des appels (OBLIGATOIRE)
Dans TOUS les fichiers de `fsdeploy/lib/ui/screens/` :
- RECHERCHER : `self.app.bus.emit(`
- REMPLACER PAR : `self.bridge.emit(`

## 🛠 ACTION 3 : Nettoyage
- Supprimer `from fsdeploy.lib.bus import MessageBus` si plus utilisé.
