# add.md — 24.1.d : Branchement Final

## ⚡️ ACTION : Redirection du Flux
Dans tous les fichiers `.py` de `fsdeploy/lib/ui/screens/` :

1. **Substitution** :
   * Chercher : `self.app.bus.emit(`
   * Remplacer par : `self.bridge.emit(`

2. **Vérification des Imports** :
   * S'assurer que `SchedulerBridge` est importé.
   * Supprimer l'import de `MessageBus` s'il n'est plus utilisé.

> **CONSIGNE DE SÉCURITÉ** : Procède écran par écran ou par petits groupes. Ne tente pas de modifier les 23 fichiers dans un seul bloc SEARCH/REPLACE pour éviter la corruption de fichier.
