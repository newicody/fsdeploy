# add.md — 38.3 : Adaptation du Graphe et Sécurisation

## 🛠 1. Adaptation du Resolver (lib/resolver.py)
- **Lazy Loading des variables** : Modifier la méthode qui génère la commande finale. Elle doit aller chercher les valeurs dans l'objet fusionné `ConfigObj` juste avant l'envoi au Scheduler.
- **Vérification de l'État du Graphe** : S'assurer que si une tâche parente échoue, le Resolver marque immédiatement toutes les tâches dépendantes comme `SKIPPED` et demande au Scheduler de nettoyer la cage (`umount`).

## 🛠 2. Renforcement du Security Hook
- Localiser le hook de sécurité actuel et l'étendre :
    - **Validation de Paramètres** : Ajouter une étape de vérification via Regex ou Liste Noire sur les arguments injectés (ex: empêcher l'injection de commandes via des noms de pool ZFS malveillants).
    - **Vérification Hardware** : Le hook doit consulter `detected.ini` pour interdire toute action root sur les périphériques marqués comme "critiques" ou "système".

## 🛠 3. Branchement au Scheduler (lib/scheduler.py)
- Le Scheduler doit recevoir un objet `TaskNode` (issu du graphe) et non plus une simple commande.
- **Traitement du Contexte** :
    - Lire `node.environment` : Si `cage`, activer le cycle `mount_api` -> `chroot` -> `umount`.
    - Lire `node.privileged` : Si `true`, invoquer le tunnel `sudo -S -k`.

## 🛠 4. Unification de la Config d'Intention
- Vérifier que `intents.ini` utilise bien les clés standardisées que nous avons définies :
    - `requires` / `parent` pour la hiérarchie.
    - `policy` pour le niveau de sécurité.
    - `env` pour le contexte d'exécution.

## 🛠 5. Refactor UI / Bridge
- Nettoyer les écrans pour s'assurer qu'aucun ne court-circuite le Resolver.
- Chaque action doit être une "soumission d'intention" au Bridge, qui la passe au Resolver pour validation.
