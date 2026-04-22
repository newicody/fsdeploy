# add.md — 38.4 : Bridge asynchrone et Agent Sudo

## 🛠️ 1. Évolution du Bridge (lib/bridge.py)
- Créer le canal `INTENT_REQUEST` :
    - L'UI envoie un `intent_id`.
    - Le Bridge interroge le Scheduler : "Est-ce que cette branche du graphe a besoin de root ?"
- Si oui : Le Bridge déclenche `app.push_screen(SudoModal)`.

## 🛠️ 2. Le SudoModal (lib/ui/modals/sudo.py)
- Créer un écran Textual minimaliste :
    - Champ `Input(password=True)`.
    - Bouton "Valider" qui renvoie le pass au Bridge (via un callback ou un message).
    - **Sécurité** : Le mot de passe ne doit être stocké dans aucune variable globale. Il doit être transmis directement au Scheduler qui l'injectera dans le pipe `stdin` puis sera effacé.

## 🛠️ 3. Streamer de Logs (UI Feedback)
- Adapter le Scheduler pour qu'il émette un signal `TASK_LOG` à chaque ligne de sortie de `subprocess`.
- Le Bridge doit capturer ce signal pour mettre à jour une `RichLog` ou un widget de terminal dans l'écran actif.

## 🛠️ 4. Refactoring des Écrans (Modèle)
- Choisir un écran (ex: `ZfsPoolScreen`) et appliquer le nouveau paradigme :
    - Supprimer : `subprocess.run(...)`.
    - Ajouter : `self.bridge.emit("EXECUTE", {"id": "ZFS_CREATE_POOL", "data": {"name": "data"}})`.
