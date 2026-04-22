# add.md — 38.2 : Implémentation du Runner Multi-Mode

## 🛠 1. Logique de décision (lib/scheduler.py)
- Créer une fonction `execute_from_config(section_name)` :
    - Récupérer les clés `mode`, `root`, `command` dans ConfigObj.
    - Déterminer le tunnel d'exécution.

## 🛠 2. Le tunnel Chroot (L'Isolation)
- Créer une méthode privée `_prepare_cage()` :
    - `sudo mount --bind /dev /opt/fsdeploy/bootstrap/dev` (et ainsi de suite pour proc et sys).
- Créer une méthode privée `_cleanup_cage()` :
    - `sudo umount -l /opt/fsdeploy/bootstrap/dev` (le `-l` est important pour éviter les blocages).

## 🛠 3. Injection Sudo (La Sécurité)
- Utiliser `subprocess.Popen` avec `stdin=PIPE`.
- Récupérer le mot de passe depuis le Bridge (via le SudoModal).
- Envoyer : `process.communicate(input=f"{password}\n".encode())`.

## 🛠 4. Test sur une section ZFS
- Prendre une section ZFS de ta config comme cobaye.
- Vérifier que la commande s'exécute bien dans le chroot sans laisser de traces sur l'hôte.
