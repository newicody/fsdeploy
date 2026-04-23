# add.md — 39.6 : Feedback Temps Réel et Sudo Agent

## 🛠️ 1. L'Agent Sudo (lib/bridge.py)
- **Protocole de Secret** : 
    - Le Scheduler émet `SIGNAL_NEED_PASSWORD` quand il bloque sur un tunnel Sudo.
    - Le Bridge met le Worker en pause et déclenche la `SudoModal` sur l'UI.
    - Une fois validé, le secret est injecté dans le pipe `stdin` du processus de la Cage.
- **Sécurité** : La variable `password` doit être écrasée/supprimée (`del`) immédiatement après injection.

## 🛠️ 2. Streamer de Logs (UI Feedback)
- Mapper les sorties `stdout` et `stderr` de la cage vers le signal `TASK_LOG` du Bridge.
- Chaque écran d'action doit intégrer un widget `RichLog`.
- **Règle d'Or** : Les logs doivent être asynchrones. L'UI doit rester réactive pendant que les commandes lourdes (formatage, extraction) tournent.

## 🛠️ 3. Gestionnaire de Sortie (Failsafe)
- Dans `main.py`, implémenter une capture globale des signaux de sortie.
- **Action** : Si l'utilisateur quitte brusquement l'app, le Bridge doit forcer `Scheduler.cleanup_cage()` pour démonter les points de montage bind sur l'hôte.

## 🛠️ 4. Audit de Validation "Zero-OS"
- Vérifier les derniers fichiers dans `lib/ui/screens/`.
- S'assurer qu'aucun import `os` ou `subprocess` n'a survécu.
- Tout ce qui touche au disque ou au réseau doit être une intention transmise au Bridge.
