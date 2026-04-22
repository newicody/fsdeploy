# add.md — 38.2 : Centralisation de l'Exécution via le Scheduler

## 🛠 1. Intégration de la Logique de Configuration
- Le Scheduler doit charger les fichiers `.ini` via **ConfigObj**.
- **Audit des Clés** : Identifier dans la configuration les clés qui pilotent l'exécution (ex: `sudo=true`, `environment=chroot`).
- **Mapping des Intents** : Faire en sorte que le Scheduler reconnaisse quel bloc de configuration correspond à quelle intention envoyée par le Bridge.

## 🛠 2. Implémentation du Multi-Mode Runner
Modifier le moteur d'exécution du Scheduler pour gérer trois flux distincts :
- **MODE A (Standard)** : Exécution via `subprocess.run` classique pour les tâches informatives.
- **MODE B (Sudo Host)** : 
    - Déclenchement : `sudo=true` dans la config.
    - Action : Utiliser `subprocess.Popen(['sudo', '-S', '-k', ...])`.
    - Injection : Envoyer le mot de passe (reçu du Bridge) via `stdin.write`.
- **MODE C (Sudo Chroot)** :
    - Déclenchement : `environment=chroot` dans la config.
    - Pré-requis : Monter `/dev`, `/proc`, `/sys` en bind dans `/opt/fsdeploy/bootstrap`.
    - Action : `sudo -S -k chroot /opt/fsdeploy/bootstrap {cmd}`.
    - Post-requis : Démonter proprement les API kernel après la tâche.

## 🛠 3. Liaison Bridge <-> Scheduler (Auth Flow)
- Si le Scheduler détecte un besoin de `sudo` :
    1. Envoyer un signal de "pause" au Bridge.
    2. Demander au Bridge d'afficher le `SudoModal`.
    3. Attendre la réception du password avant de lancer le Runner.
    4. **Sécurité** : Ne jamais stocker le mot de passe dans un fichier, uniquement en mémoire vive pour la durée de la tâche.

## 🛠 4. Nettoyage de l'UI (Début de l'Audit)
- Commencer par les écrans de montage/partitionnement.
- Remplacer toute logique de manipulation de fichiers (`os`, `shutil`) ou d'appels `subprocess` par l'émission d'une intention vers le Bridge.
- Exemple : `self.bridge.emit("EXECUTE_CONFIG", {"id": "mount_zfs_overlay"})`.
