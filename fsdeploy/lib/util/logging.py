"""
Configuration de la journalisation pour fsdeploy.
"""

import logging
import logging.handlers
import sys
from pathlib import Path


def setup_logging(console_level=logging.INFO, log_file=None):
    """Configure la journalisation pour fsdeploy.

    Args:
        console_level: niveau pour le handler console (stderr).
        log_file: chemin complet du fichier de log. Si None, utilise
                  var/log/fsdeploy/fsdeploy.log.
    """
    if log_file is None:
        log_dir = Path("var/log/fsdeploy")
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "fsdeploy.log"
    else:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()

    # Nettoyer les handlers existants (si on appelle plusieurs fois)
    for hdlr in root_logger.handlers[:]:
        root_logger.removeHandler(hdlr)

    # Formatter commun
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Handler console (stderr)
    console = logging.StreamHandler(sys.stderr)
    console.setLevel(console_level)
    console.setFormatter(formatter)
    root_logger.addHandler(console)

    # Handler fichier rotatif
    file_handler = logging.handlers.RotatingFileHandler(
        str(log_file),
        maxBytes=10 * 1024 * 1024,   # 10 Mo
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    root_logger.setLevel(logging.INFO)
