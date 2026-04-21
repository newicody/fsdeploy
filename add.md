# add.md — 24.2 : Tickets & Launch

## 1. Fichier `launch.sh`
- Réécrire le script pour inclure :
  ```bash
  export PYTHONPATH=$PYTHONPATH:$(pwd)
  # Tuer les instances précédentes
  pkill -f "python3 -m fsdeploy" || true
  python3 -m fsdeploy.lib.ui.app
