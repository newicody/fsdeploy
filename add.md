# add.md — 38.3 : Runtime Injector et Orchestration de la Cage

## 🛠️ 1. Runtime Variable Injector (lib/scheduler/injector.py)
- Créer une fonction `resolve_command(raw_command, config_obj)` :
    - Utilise les variables de la section `[DETECTED]` pour remplir les `{placeholders}`.
    - **Sécurité** : Nettoyer les valeurs injectées pour empêcher tout "command injection" (interdire `;`, `&`, `|` dans les variables dynamiques).
    - **Fallback** : Si une variable est absente (ex: `{target_disk}` n'est pas défini), lever une erreur explicite pour stopper le graphe.

## 🛠️ 2. Gestionnaire de la Cage (lib/scheduler/cage.py)
- Implémenter le cycle de vie sécurisé pour le mode `chroot` :
    - `enter_cage()` : Effectue les `mount --bind` de `/dev`, `/proc`, `/sys`, `/run` vers `/opt/fsdeploy/bootstrap`.
    - `exit_cage()` : Effectue les `umount -l` (lazy unmount).
- **Robustesse** : Utiliser un bloc `try...finally` dans le Scheduler pour garantir que `exit_cage()` est appelé même si la commande ZFS ou APT échoue ou est interrompue.

## 🛠️ 3. Le Runner Multi-Mode (lib/scheduler/runner.py)
- Développer le moteur d'exécution basé sur `subprocess.Popen` :
    - **Flux Standard** : Exécution simple.
    - **Flux Sudo** : Lancer `sudo -S -k`, attendre le signal du Bridge pour injecter le mot de passe dans `stdin`.
    - **Flux Chroot** : Préparer la cage, exécuter la commande via `chroot`, nettoyer la cage.
- **Log Streaming** : Capturer `stdout` et `stderr` ligne par ligne et les émettre vers le Bridge pour que l'UI puisse afficher la progression réelle (ex: logs d'installation de paquets).

## 🛠️ 4. Validation des Nœuds (Security Hook)
- Juste avant l'exécution, comparer la commande finale avec la politique de `defaults.ini`.
- Vérifier que les disques ciblés ne sont pas dans la liste d'exclusion des périphériques système.
