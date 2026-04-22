# add.md — 38.2 : Logique d'Exécution du Scheduler

## 🛠 1. Initialisation du Scheduler (lib/scheduler.py)
- Charger l'instance globale de la configuration via **ConfigObj**.
- Créer une méthode `resolve_context(section_id)` qui identifie si une tâche doit s'exécuter sur l'hôte ou dans la cage, et si elle nécessite `sudo`.

## 🛠 2. Implémentation du Runner Sécurisé
Développer la fonction `run_intent(intent_id, password=None)` :
- **Si Sudo requis** : 
    - Utiliser `subprocess.Popen` avec les arguments `['sudo', '-S', '-k', '--', 'command']`.
    - Envoyer le `password` dans `stdin`.
- **Si Chroot requis** :
    - Exécuter (via sudo) les montages bind : `/dev`, `/proc`, `/sys` vers `/opt/fsdeploy/bootstrap/`.
    - Encapsuler la commande : `chroot /opt/fsdeploy/bootstrap /bin/bash -c "la_commande"`.
    - **Sécurité** : Utiliser un bloc `finally` pour garantir le `umount` des API kernel après l'action.

## 🛠 3. Bridge : Gestion du challenge d'authentification
- Le Bridge intercepte l'appel du Scheduler.
- Si le Scheduler renvoie un code `AUTH_REQUIRED` :
    - Le Bridge appelle `app.push_screen(SudoModal)`.
    - Une fois le pass reçu, il relance la tâche dans le Scheduler.

## 🛠 4. Nettoyage de l'UI (Exemple : ZFS ou Partitions)
- Prendre un écran de montage comme modèle.
- Supprimer `import os` et `import subprocess`.
- Remplacer le clic du bouton par : 
  `self.bridge.emit("EXECUTE", {"config_id": "ma_section_zfs"})`.
