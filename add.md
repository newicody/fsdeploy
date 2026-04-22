# add.md — 38.4 : Bridge Asynchrone et Capture de Secret

## 🛠️ 1. Évolution du Bridge (lib/bridge.py)
- Créer le canal `EXECUTE_INTENT(intent_id, data)` :
    - Le Bridge reçoit la demande de l'UI.
    - Il interroge le Resolver pour obtenir le plan de bataille (le graphe résolu).
    - Il demande au Scheduler : "Est-ce qu'une de ces tâches nécessite root ?".

## 🛠️ 2. L'Agent d'Authentification (SudoModal)
- Créer `lib/ui/modals/sudo_modal.py` :
    - Un écran `ModalScreen` Textual avec un `Input(password=True)`.
    - **Le Flux** : Le Bridge appelle la modale -> L'utilisateur saisit -> Le pass est envoyé directement au Scheduler via un signal privé -> La modale se ferme et le pass est "oublié" par l'UI.

## 🛠️ 3. Streamer de Logs (Feedback UI)
- Modifier le Scheduler pour qu'il émette un message `MSG_LOG(text)` à chaque ligne capturée sur `stdout/stderr`.
- Le Bridge doit relayer ces messages à l'écran actif (ex: dans un widget `RichLog`) pour que l'utilisateur voie ZFS travailler en temps réel.

## 🛠️ 4. Transition du Premier Écran (Test)
- Prendre l'écran de gestion des disques ou des pools.
- **Action** : Supprimer toute logique de `subprocess`.
- **Nouveau Code** : 
  `self.bridge.emit("EXECUTE_INTENT", {"id": "ZFS_POOL_CREATE", "params": self.get_form_data()})`
