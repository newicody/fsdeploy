# add.md — 24.1 : Finalisation Bridge

## 🛠 ACTION 1 : Initialisation manquante
Dans `fsdeploy/lib/ui/screens/`, pour CHAQUE fichier n'ayant pas encore le Bridge :
- Ajouter : `from fsdeploy.lib.ui.bridge import SchedulerBridge`
- Dans `on_mount` : `self.bridge = SchedulerBridge.default()`

## 🛠 ACTION 2 : Branchement des commandes (CRITIQUE)
Dans TOUS les fichiers du dossier `screens/` :
- RECHERCHER : `self.app.bus.emit(`
- REMPLACER PAR : `self.bridge.emit(`

## 🛠 ACTION 3 : Nettoyage
- Supprimer `from fsdeploy.lib.bus import MessageBus` si le fichier n'utilise plus le bus directement.
