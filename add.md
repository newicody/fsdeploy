# add.md — 38.5 : Migration de l'Écran ZFS vers les Intentions

## 🛠️ 1. Nettoyage de l'écran (ZfsPoolScreen.py)
- **Suppression radicale** : Enlever tous les imports `subprocess` et la logique de manipulation de chaînes de caractères pour les commandes ZFS.
- **Simplification** : L'écran ne doit plus que collecter les données du formulaire (nom du pool, disques sélectionnés, options).

## 🛠️ 2. Émission de l'Intention
- Remplacer l'ancien code d'exécution par :
  `self.bridge.emit("EXECUTE_INTENT", {"id": "ZFS_POOL_CREATE", "params": data})`

## 🛠️ 3. Gestion du Feedback (Real-time Logs)
- Connecter le widget de log de l'écran au signal `TASK_LOG` émis par le Bridge.
- L'utilisateur doit voir le texte défiler pendant que le Scheduler travaille dans la cage.

## 🛠️ 4. Test de Sécurité
- Tenter de créer un pool sur un disque déjà utilisé ou protégé.
- Vérifier que le **Security Hook** du Resolver renvoie une erreur propre sans même que le Scheduler ne tente l'action.
