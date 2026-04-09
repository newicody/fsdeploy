"""
fsdeploy.log
=============
Configuration structlog pour les trois contextes (live, initramfs, booted).

Detecte automatiquement :
  - TERM=linux → framebuffer → fallback ASCII (pas de couleurs ANSI fancy)
  - Mode debug/verbose/quiet via arguments ou config
  - Format text (console) ou json (structlog JSON lines)

Usage :
    from log import setup_logging, get_logger

    setup_logging(level="debug", verbose=True)
    log = get_logger("detection")
    log.info("pool_detected", pool="boot_pool", state="ONLINE")
"""

import os
import sys
import logging
from pathlib import Path
from typing import Optional

try:
    import structlog
    HAS_STRUCTLOG = True
except ImportError:
    HAS_STRUCTLOG = False


# ── Detection framebuffer ─────────────────────────────────────────────────────

IS_FRAMEBUFFER = os.environ.get("TERM") == "linux"


# ── Niveau de log ─────────────────────────────────────────────────────────────

LEVEL_MAP = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
}


def setup_logging(
    level: str = "info",
    verbose: bool = False,
    debug: bool = False,
    quiet: bool = False,
    log_format: str = "text",
    log_dir: str = "",
    ascii_fallback: Optional[bool] = None,
) -> None:
    """
    Configure le systeme de logging.

    Args:
        level:     debug | info | warning | error
        verbose:   Force le niveau a debug + affiche les commandes
        debug:     Force le niveau a debug + traces internes
        quiet:     Niveau error uniquement
        log_format: text | json
        log_dir:   Repertoire pour les fichiers de log (vide = pas de fichier)
        ascii_fallback: Force le mode ASCII (None = auto-detect via TERM)
    """
    # Resoudre le niveau
    if debug or verbose:
        effective_level = "debug"
    elif quiet:
        effective_level = "error"
    else:
        effective_level = level

    log_level = LEVEL_MAP.get(effective_level, logging.INFO)

    # ASCII fallback
    use_ascii = ascii_fallback if ascii_fallback is not None else IS_FRAMEBUFFER

    if HAS_STRUCTLOG:
        _setup_structlog(log_level, log_format, use_ascii, log_dir)
    else:
        _setup_stdlib(log_level, log_dir)


def _setup_structlog(level: int, fmt: str, ascii_mode: bool,
                     log_dir: str) -> None:
    """Configure structlog avec le bon renderer."""

    # Processors communs
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=False),
        structlog.processors.StackInfoRenderer(),
    ]

    if fmt == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        if ascii_mode:
            # Framebuffer : pas de couleurs, pas de caracteres fancy
            processors.append(_ascii_renderer)
        else:
            processors.append(
                structlog.dev.ConsoleRenderer(
                    colors=sys.stderr.isatty(),
                    pad_event=40,
                )
            )

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )

    # Fichier de log
    if log_dir:
        _setup_file_handler(log_dir, level)


def _setup_stdlib(level: int, log_dir: str) -> None:
    """Fallback : logging stdlib si structlog n'est pas installe."""
    fmt = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
    datefmt = "%H:%M:%S"

    handlers = [logging.StreamHandler(sys.stderr)]

    if log_dir:
        log_path = Path(log_dir) / "fsdeploy.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(str(log_path)))

    logging.basicConfig(
        level=level,
        format=fmt,
        datefmt=datefmt,
        handlers=handlers,
    )


def _setup_file_handler(log_dir: str, level: int) -> None:
    """Ajoute un handler fichier pour la persistance."""
    log_path = Path(log_dir) / "fsdeploy.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    file_handler = logging.FileHandler(str(log_path))
    file_handler.setLevel(level)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    )

    # Ajouter au root logger (structlog utilise PrintLogger,
    # mais les messages passent aussi par stdlib si configure)
    logging.getLogger().addHandler(file_handler)


def _ascii_renderer(logger, method_name, event_dict):
    """
    Renderer ASCII pour framebuffer (TERM=linux).

    Pas de couleurs ANSI, pas de caracteres Unicode fancy.
    Format : [HH:MM:SS] LEVEL  event  key=value key=value
    """
    ts = event_dict.pop("timestamp", "")
    level = event_dict.pop("level", "info").upper()
    event = event_dict.pop("event", "")

    # Formater les key=value
    kv_parts = []
    for k, v in sorted(event_dict.items()):
        if k.startswith("_"):
            continue
        kv_parts.append(f"{k}={v}")

    kv_str = "  ".join(kv_parts)
    line = f"[{ts}] {level:7s} {event}"
    if kv_str:
        line += f"  {kv_str}"

    return line


# ── Logger factory ────────────────────────────────────────────────────────────

def get_logger(name: str = "fsdeploy"):
    """
    Retourne un logger structure.

    Usage :
        log = get_logger("detection")
        log.info("pool_found", pool="boot_pool")
        log.warning("mount_failed", dataset="tank/home", error="busy")
    """
    if HAS_STRUCTLOG:
        return structlog.get_logger(name)
    else:
        return logging.getLogger(name)
