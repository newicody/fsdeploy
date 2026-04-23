# add.md — 40.0 : Feedback Temps Réel et Sudo Agent

## 🛠️ 1. Finalisation de l'Agent Sudo (lib/bridge.py)
- **Protocole de Secret** : 
    - Le Scheduler émet `SIGNAL_NEED_PASSWORD` s'il bute sur un tunnel privilègié.
    - Le Bridge met le Worker en pause et déclenche la `SudoModal`.
    - Injection du secret dans le pipe `stdin` du runner et purge immédiate de la variable en mémoire.

## 🛠️ 2. Streamer de Logs (Feedback Visuel)
- Connecter les flux `stdout/stderr` du Scheduler au signal `TASK_LOG`.
- **UI** : Intégrer un widget `RichLog` dans chaque écran d'action.
- **Objectif** : Que l'utilisateur voie la progression réelle (ex: les étapes de `zpool create`) sans latence.

## 🛠️ 3. Gestionnaire de Signaux Global
- Dans `main.py`, capturer les interruptions système (Ctrl+C, fermeture de fenêtre).
- **Action** : Déclencher impérativement `Scheduler.cleanup_cage()` avant de quitter pour libérer les points de montage bind sur l'hôte.

## 🛠️ 4. Audit Final des Screens
- Une dernière passe pour s'assurer qu'aucun `os.path` ou `shutil` résiduel ne traîne dans les 23 fichiers de `lib/ui/screens/`.