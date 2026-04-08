import sys
from pathlib import Path

# Ajoute le répertoire racine du projet au PYTHONPATH
root_dir = Path(__file__).parent.parent.absolute()
sys.path.insert(0, str(root_dir))
