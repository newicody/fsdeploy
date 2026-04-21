# add.md — 27.1 : Restauration Système

## 🛠 ACTION 1 : Analyse de l'historique
- Examine l'ancienne version de `launch.sh` (avant le commit c0d7262).
- Identifie les blocs : `install_dependencies()`, `check_live_environment()`, et la gestion du `PYTHONPATH`.

## 🛠 ACTION 2 : Fusion du script launch.sh
- Le nouveau `launch.sh` doit IMPÉRATIVEMENT :
  1. Vérifier si on est sur un système Debian Live.
  2. Installer les dépendances système manquantes (apt-get).
  3. Créer/Activer le venv et installer `requirements.txt`.
  4. Lancer `fsdeploy.lib.ui.app` avec le bon `PYTHONPATH`.

## 🛠 ACTION 3 : Vérification des versions
- Compare `requirements.txt` avec la version de sauvegarde.
- Fixe les versions : `textual==X.X.X` et `rich==X.X.X` pour garantir la stabilité de l'UI.
