# add.md — 38.6 : Stream de Status et Orchestration UI

## 🛠️ 1. Streamer de Logs (lib/bridge.py)
- Mettre en place l'abonnement aux événements du Scheduler.
- **Logique** : Chaque ligne de `stdout` capturée par le `subprocess.Popen` dans la cage doit être émise vers le Bridge avec un tag de sévérité (INFO, WARN, ERROR).

## 🛠️ 2. Gestion de l'Interruption (lib/scheduler/runner.py)
- Implémenter le `StopSignal` : Si l'utilisateur clique sur "Annuler" dans l'UI, le Bridge doit envoyer un `SIGTERM` au processus dans la cage.
- **Sécurité** : Le bloc `finally` du Scheduler doit impérativement déclencher le `cleanup_cage()` (les umounts) même sur une interruption manuelle.

## 🛠️ 3. Migration des 23 Écrans (Méthode)
- Appliquer la règle "Zero-OS" :
    - Tout écran contenant `os.path`, `shutil` ou `subprocess` doit être refactorisé.
    - Ces actions doivent devenir des entrées dans `intents.ini`.
    - L'écran ne doit plus faire que de la validation de formulaire et de l'affichage de progression.

## 🛠️ 4. Test du SudoModal
- Valider le cas où le Scheduler demande le privilège root au milieu d'une chaîne de tâches.
- Vérifier que l'UI affiche la modale, bloque l'attente, et reprend l'exécution une fois le secret transmis.
