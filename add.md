# add.md — 38.2 : Branchement du Scheduler sur les champs Config

## 🛠 1. Centralisation de la Configuration
- Modifier `lib/scheduler.py` pour qu'il soit le seul à manipuler les appels système.
- **Lecture de Config** : Le Scheduler doit charger les fichiers ConfigObj du dépôt pour identifier les sections d'action.

## 🛠 2. Implémentation du Runner Multi-Mode
Le Scheduler doit implémenter une fonction d'exécution qui choisit son tunnel selon la config :
- **Mode Standard** : Exécution simple via le `venv`.
- **Mode Sudo Host** : 
    - Déclenché par les drapeaux de privilèges dans la config.
    - Utilise `subprocess.Popen(['sudo', '-S', '-k', ...])`.
    - Demande le pass au Bridge (qui affiche le `SudoModal`) et l'injecte dans `stdin`.
- **Mode Sudo Chroot** :
    - Déclenché par les drapeaux de contexte/cage dans la config.
    - Automatisme : `mount --bind` des API kernel (`/dev`, `/proc`, `/sys`) dans `/opt/fsdeploy/bootstrap`.
    - Exécution : `chroot` vers la cage avec injection du pass.
    - Nettoyage : `umount` systématique après l'action.

## 🛠 3. Liaison par "Intents" (Bridge)
- Le Bridge ne doit plus faire passer de commandes brutes.
- L'UI envoie un `config_id` (ex: `zfs_pool_setup`).
- Le Scheduler récupère la section associée dans ConfigObj et exécute selon les paramètres définis.

## 🛠 4. Nettoyage des Écrans (Audit)
- Parcourir les 23 écrans de `lib/ui/screens/`.
- **Action** : Supprimer tous les `import os`, `subprocess`, `shutil`.
- **Remplacement** : Toutes les actions de boutons doivent devenir des `self.bridge.emit("EXECUTE_TASK", {"id": "NOM_SECTION_CONFIG"})`.
