#!/usr/bin/env python3
"""
fsdeploy — Point d'entrée principal.
Gestionnaire de signaux global pour le nettoyage de la cage.
"""

import signal
import sys


def _handle_termination(signum, frame):
    try:
        from fsdeploy.lib.scheduler.cage import cleanup_cage
        cleanup_cage()
    except Exception:
        pass
    sys.exit(128 + signum)


signal.signal(signal.SIGINT, _handle_termination)
signal.signal(signal.SIGTERM, _handle_termination)
if hasattr(signal, 'SIGHUP'):
    signal.signal(signal.SIGHUP, _handle_termination)


def main():
    from fsdeploy.lib.ui.app import FsDeployApp
    app = FsDeployApp()
    app.run()


if __name__ == "__main__":
    main()
