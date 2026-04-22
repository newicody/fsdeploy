# add.md — 38.3 : Implémentation du Runner Multi-Mode

## 🛠 1. Architecture du Scheduler (lib/scheduler.py)
Le Scheduler doit maintenant consommer les nœuds validés par le Resolver :
- **Entrée** : Un objet `TaskNode` contenant la commande résolue, le contexte (`env`) et le niveau de privilège (`root`).
- **Sortie** : Un flux de statut vers le Bridge (Progress, Success, Error).

## 🛠 2. Implémentation du "Tunnel" Sudo
Pour les tâches marquées `root=true` :
- Utiliser `subprocess.Popen(['sudo', '-S', '-k', '--', ...], stdin=PIPE, stdout=PIPE, stderr=PIPE)`.
- **Mécanisme** : Le Scheduler demande le secret au Bridge, puis l'injecte via `process.communicate(input=f"{password}\n".encode())`.
- **Sécurité** : Utiliser `sudo -k` pour s'assurer que le mot de passe ne reste pas en cache système.

## 🛠 3. Implémentation du "Tunnel" Chroot (La Cage)
Pour les tâches marquées `env=chroot` :
- **Pré-exécution** : Monter les API kernel nécessaires dans `/opt/fsdeploy/bootstrap` :
  `mount --bind /dev`, `/proc`, `/sys`.
- **Exécution** : Lancer la commande via `chroot /opt/fsdeploy/bootstrap {command}`.
- **Post-exécution** : Bloc `finally` obligatoire pour exécuter `umount -l` sur tous les points de montage bind, même en cas de crash de la tâche.

## 🛠 4. Sécurité Contextuelle (Validation finale)
- Avant de lancer le tunnel, le Scheduler effectue un dernier check :
  "Est-ce que les arguments de la commande (ex: `/dev/sda`) sont cohérents avec les politiques définies dans `defaults.ini` ?"
- Si une incohérence est détectée (ex: tentative de modification d'un disque protégé), le Scheduler avorte la tâche et marque le nœud comme `BLOCKED`.

## 🛠 5. Liaison UI
- Adapter le Bridge pour qu'il serve de relais entre le Scheduler et le `SudoModal`.
- S'assurer que le mot de passe n'est jamais stocké, mais uniquement transmis au pipe `stdin` du processus.
