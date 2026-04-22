# add.md — 38.2 : Branchement du Scheduler sur les champs Config

## 🛠 1. Analyse des champs ConfigObj
- Modifier `lib/scheduler.py` pour qu'il charge systématiquement la configuration au démarrage.
- **Logique de décision** :
    - Si une section contient une clé de type `privileged=true` ou `sudo=1` -> Mode Sudo.
    - Si une section contient `context=chroot` ou `use_cage=true` -> Mode Chroot.
    - Extraire dynamiquement les commandes et arguments depuis les champs de la section.

## 🛠 2. Implémentation du Runner Multi-Mode
- **Mode Standard** : Exécuter directement via le `venv`.
- **Mode Sudo** : 
    - Appeler `self.bridge.ask_sudo()` pour déclencher le `SudoModal`.
    - Exécuter `sudo -S -k {command}` via `subprocess.Popen`.
    - Injecter le mot de passe dans `stdin`.
- **Mode Chroot** : 
    - Monter `/dev`, `/proc`, `/sys` dans `/opt/fsdeploy/bootstrap`.
    - Lancer `sudo -S -k chroot /opt/fsdeploy/bootstrap {command}`.
    - Démonter les API kernel après exécution (même en cas d'erreur).

## 🛠 3. Mise à jour du Bridge (D-Bus style)
- Le Bridge ne doit plus accepter de chaînes de caractères "commandes".
- Il doit recevoir un `config_id` (ex: `zfs_create_pool`).
- Le Bridge transmet cet ID au Scheduler qui se charge de trouver la "recette" dans la config.

## 🛠 4. Audit des 23 Écrans
- Supprimer les imports `os`, `subprocess` et `shutil`.
- Remplacer les fonctions de boutons par : 
  `self.bridge.emit("RUN_TASK", {"id": "NOM_DE_LA_SECTION_CONFIG"})`.
