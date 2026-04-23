# add.md — 38.6 : Feedback Temps Réel et Nettoyage de l'UI

## 🛠️ 1. Streamer de Logs (lib/bridge.py)
- Connecter le Bridge aux sorties du Scheduler.
- **Signal `TASK_LOG`** : Chaque ligne générée dans la cage doit être émise vers l'écran actif.
- **Signal `TASK_PROGRESS`** : Mettre à jour les barres de progression en fonction du nombre de nœuds terminés dans le graphe.

## 🛠️ 2. Agent de Sécurité (lib/ui/modals/sudo.py)
- Finaliser le `SudoModal` pour qu'il soit appelé par le Bridge uniquement quand le Scheduler rencontre une tâche `privileged=true`.
- S'assurer que le secret est "brûlé" (effacé de la mémoire) dès que le pipe `stdin` du processus est fermé.

## 🛠️ 3. Application de la Politique "Zero-OS"
- Prendre l'un des 23 écrans (ex: `ZfsPoolScreen`) et supprimer :
    - `import subprocess`, `import os`, `import shutil`.
- Remplacer toute la logique par un appel d'intention :
  `self.bridge.emit("EXECUTE_INTENT", {"id": "ZFS_CREATE", "params": {...}})`

## 🛠️ 4. Gestion du Nettoyage (Failsafe)
- S'assurer que si l'utilisateur ferme l'application violemment, le signal `SIGTERM` est propagé à la cage et que le `cleanup_cage` (umount) est bien exécuté.
