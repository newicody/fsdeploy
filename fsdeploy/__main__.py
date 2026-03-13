"""
python3 -m fsdeploy
Point d'entrée principal.
"""

import sys

def main() -> None:
    # Import tardif : l'UI textual n'est chargée qu'ici
    from fsdeploy.config import FsDeployConfig
    from fsdeploy.ui.app import FsDeployApp

    # Charger (ou créer) la config
    cfg = FsDeployConfig.default(create=True)

    app = FsDeployApp(cfg)
    app.run()


if __name__ == "__main__":
    main()
