# add.md — 38.1 : Bootstrap Adaptatif & Isolation (Cage)

## 🛠 1. Script launch.sh (Élévation & Détection)
- **Privilèges** : Si `EUID != 0`, tester la présence de `sudo` pour relancer, sinon solliciter `su -c "$0 $@"`.
- **Analyse Distro** :
    - Lire `/etc/os-release`.
    - Si `trixie` : Utiliser les dépôts `main contrib non-free-firmware non-free`.
    - Si `bookworm` : Utiliser `main contrib non-free` + `bookworm-backports`.
- **Update** : `apt update`.

## 🛠 2. Installation Hôte (ZFS & Tools)
- Installer : `zfsutils-linux`, `debootstrap`, `python3-venv`.
- **Spécificité Bookworm** : Forcer l'installation de ZFS via les backports (`apt install -y -t bookworm-backports zfsutils-linux`).
- Charger le module : `modprobe zfs`.

## 🛠 3. Construction de la Cage (Chroot)
- Dossier cible : `/opt/fsdeploy/bootstrap`.
- Action : `debootstrap --variant=minbase $CODENAME /opt/fsdeploy/bootstrap`.
- **Préparation Interne** :
    - Copier `/etc/apt/sources.list` vers `/opt/fsdeploy/bootstrap/etc/apt/`.
    - Exécuter `chroot /opt/fsdeploy/bootstrap apt update`.
    - Installer `zfsutils-linux` dans la cage pour les opérations de montage isolées.

## 🛠 4. Environnement Python (Venv)
- Créer `./venv` à la racine de l'application.
- Installer les dépendances : `./venv/bin/pip install -r requirements.txt`.
- **Permissions** : Appliquer `chown -R $SUDO_USER:$SUDO_USER .` pour garantir que l'utilisateur non-root possède les droits sur le projet et son venv.

## 🛠 5. Point d'entrée (__main__.py)
- Ajouter la logique de "Self-Swap" au début du fichier pour forcer l'usage du venv :
  ```python
  import sys, os
  venv_py = os.path.join(os.path.dirname(__file__), "..", "venv", "bin", "python3")
  if os.path.exists(venv_py) and sys.executable != os.path.abspath(venv_py):
      os.execv(venv_py, [venv_py] + sys.argv)
