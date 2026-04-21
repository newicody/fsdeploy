# add.md — 24.1.c : Finalisation Électrique

> **CONTEXTE** : Tous les écrans sont ouverts. Le bridge est déjà initialisé.

## 🛠 ACTION : Remplacement de masse
Dans chaque fichier du dossier `fsdeploy/lib/ui/screens/` :

1. **REPLACER** : `self.app.bus.emit(` 
2. **PAR** : `self.bridge.emit(`

## 🧹 NETTOYAGE
1. Supprimer l'import `from fsdeploy.lib.bus import MessageBus` s'il est présent.
2. S'assurer que `from fsdeploy.lib.ui.bridge import SchedulerBridge` est bien présent en haut de fichier.
