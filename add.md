# add.md — 38.5 : Migration de l'UI et Feedback Temps Réel

## 🛠️ 1. Finalisation du Feedback (lib/bridge.py)
- S'assurer que le Bridge relaie les messages suivants du Scheduler vers l'UI :
    - `TASK_START(node_id)` : Pour surligner la tâche en cours.
    - `TASK_LOG(text)` : Pour remplir le widget de console.
    - `TASK_DONE(node_id, success)` : Pour mettre à jour les barres de progression.

## 🛠️ 2. Intégration de la Capture Sudo
- Le Scheduler doit être capable de mettre l'exécution en "Pause" si le signal `NEED_AUTH` est émis.
- Une fois que le Bridge reçoit le pass via le `SudoModal`, il le transmet au Scheduler qui "Reprend" l'exécution en injectant le pass dans le pipe.

## 🛠️ 3. Modèle de Refactoring d'un Écran (ex: Partitionnement)
- **AVANT** : 150 lignes de code gérant `fdisk`, `parted`, les erreurs et les droits root.
- **APRÈS** : 
    1. Récupérer les inputs utilisateur.
    2. Envoyer une intention unique : `self.bridge.emit("EXECUTE", {"id": "PARTITION_DISK", "data": {...}})`
    3. Attendre le signal `TASK_DONE` pour passer à l'écran suivant.

## 🛠️ 4. Nettoyage de Printemps
- Parcourir les 23 écrans.
- **Action Radicale** : Supprimer tout `import subprocess`, `import os`, `import shutil`.
- Si un écran a besoin de faire une action sur le système, il **doit** passer par une intention définie dans `intents.ini`.
