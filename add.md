# add.md — 39.3 : Finalisation du Sudo Agent et Log Sync

## 🛠️ 1. L'Agent Sudo (lib/bridge.py)
- Mettre en place la "File d'attente bloquante" :
    - Si le Scheduler émet `NEED_AUTH`, il suspend le nœud courant du graphe.
    - Le Bridge affiche le `SudoModal` par-dessus l'écran actif.
    - Une fois le pass reçu, le Bridge l'injecte dans le `stdin` du Scheduler et détruit la variable en RAM.

## 🛠️ 2. Streamer de Logs Interactif
- Connecter les pipes `stdout` et `stderr` de la Cage au signal `TASK_LOG`.
- **UI** : Chaque écran doit avoir un widget `RichLog` qui défile en temps réel pendant l'action.
- **Sémantique** : Coloriser les sorties (Rouge pour les erreurs système, Vert pour le succès des tâches).

## 🛠️ 3. Gestion de l'Interruption (Failsafe)
- S'assurer que si l'utilisateur appuie sur "Quitter", le Bridge envoie un signal `SIGTERM` au processus de la Cage.
- Vérifier que la routine `cleanup_cage` s'exécute bien dans ce scénario pour libérer les ressources système.

## 🛠️ 4. Audit final des 23 Screens
- Vérification "Zéro-OS" : aucun écran ne doit importer `subprocess`.
- Remplacer les dernières manipulations de fichiers (`os.mkdir`, etc.) par des Intentions dédiées.
