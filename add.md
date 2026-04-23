# add.md — 39.4 : Finalisation du Feedback et Sécurité Sudo

## 🛠️ 1. L'Agent Sudo (lib/bridge.py)
- Créer le protocole de pause :
    - Le Scheduler émet `SIGNAL_NEED_PASSWORD`.
    - Le Bridge met le Worker en pause et affiche `SudoModal`.
    - Le secret est injecté dans le pipe `stdin` et la variable est immédiatement purgée de la RAM.

## 🛠️ 2. Stream de Log Contextuel
- Chaque écran d'action (ZFS, Partitionnement, etc.) doit afficher son propre widget de logs.
- Le Bridge doit router les logs de la tâche en cours vers l'écran actif uniquement.
- **Colorisation** : Utiliser Rich pour souligner les étapes clés (ex: "Pool Created" en vert).

## 🛠️ 3. Gestionnaire de Signaux Global
- Dans `main.py`, capturer les signaux de sortie système.
- **Action** : Si l'utilisateur quitte, forcer le `Scheduler.cleanup_cage()` pour libérer les points de montage avant de fermer le processus Python.

## 🛠️ 4. Audit final des Screens restant
- Vérifier qu'aucun écran ne tente de lire ou d'écrire un fichier directement sans passer par une intention (ex: `/etc/fstab` doit être géré par une intention `WRITE_FSTAB` dans la Cage).
