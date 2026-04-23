# add.md — 39.2 : Finalisation du Sudo Agent et Log Sync

## 🛠️ 1. L'Agent Sudo (lib/bridge.py)
- Finaliser le mécanisme `NEED_AUTH` :
    - Le Scheduler bloque sur le pipe `stdin`.
    - Le Bridge affiche la modale `SudoModal`.
    - Le secret est injecté et **immédiatement détruit de la mémoire** (`del secret`).

## 🛠️ 2. Routage sémantique des Logs
- Chaque intention dans `intents.ini` peut désormais avoir un tag de priorité.
- Le Bridge doit filtrer les logs :
    - `DEBUG` -> Uniquement dans le fichier log global.
    - `INFO/ERROR` -> Streamé en direct vers le widget `RichLog` de l'écran actif.

## 🛠️ 3. Gestion des Signaux (Failsafe)
- Implémenter un gestionnaire de sortie propre dans `main.py`.
- Si l'utilisateur quitte brusquement (Alt+F4 ou Ctrl+C), le Bridge doit envoyer un `SIGTERM` au Scheduler pour qu'il exécute sa routine de démontage (`cleanup_cage`).

## 🛠️ 4. Validation des 23 Screens (Audit Final)
- Vérification qu'aucun écran ne contient de logique "cachée".
- Chaque bouton "Action" doit obligatoirement passer par `self.bridge.emit("EXECUTE_INTENT", ...)`.
