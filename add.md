# add.md — 39.5 : Finalisation du Sudo Agent et Feedback

## 🛠️ 1. L'Agent Sudo (lib/bridge.py)
- Mettre en place le protocole de suspension :
    - Le Scheduler détecte un besoin de privilèges -> Émet `SIGNAL_NEED_AUTH`.
    - Le Bridge intercepte, affiche la modale, et met le Worker en pause.
    - Une fois le pass saisi, injection dans le pipe `stdin` du processus de la Cage.
- **Sécurité** : Purge immédiate de la variable `password` après injection.

## 🛠️ 2. Streamer de Logs Interactif
- Connecter les sorties du Scheduler au signal `TASK_LOG` du Bridge.
- Chaque écran doit posséder un widget `RichLog` abonné au canal.
- **Styling** : Utiliser le formatage Rich pour distinguer les étapes (ex: "Partitioning..." en gras, "OK" en vert).

## 🛠️ 3. Gestionnaire de Signaux Global
- Dans `main.py`, implémenter une capture de sortie (SIGINT/SIGTERM).
- **Action** : Forcer le déclenchement de `Scheduler.cleanup_cage()` pour éviter de laisser des montages bind actifs sur le système Live après la fermeture.

## 🛠️ 4. Audit Final "Zéro-OS"
- Vérifier les derniers écrans : aucune trace de `os.mkdir`, `shutil` ou `pathlib.write`. 
- Tout passage à l'acte doit être une intention `WRITE_FILE` ou `EXEC_CMD` transitant par la Cage.
