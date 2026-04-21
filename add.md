# add.md — 24.1.b : Migration Fonctionnelle Bridge

## 🎯 Objectif : Remplacement systématique et complet

Dans TOUS les fichiers de `fsdeploy/lib/ui/screens/*.py` :

1. **Initialisation** : S'assurer que `self.bridge = SchedulerBridge.default()` est présent dans `on_mount`.
2. **Remplacement Bus** : Migrer TOUS les appels :
   `self.app.bus.emit(...)`  =>  `self.bridge.emit(...)`
3. **Nettoyage** : Supprimer l'import de `MessageBus` s'il n'est plus utilisé localement.

> **IMPORTANT** : Ne touche à aucune autre partie du code (CSS, logique métier, etc.). Utilise tes outils pour traiter les écrans restants (ceux non listés dans le commit c0d7262).
