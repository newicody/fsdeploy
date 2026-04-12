"""
fsdeploy.__main__
==================
Point d'entrée CLI : python3 -m fsdeploy [OPTIONS] [COMMAND]
"""

# ═════════════════════════════════════════════════════════════════════════════
# PATH SETUP — DOIT ÊTRE AVANT TOUT AUTRE IMPORT
# ═════════════════════════════════════════════════════════════════════════════

import os
import sys
from pathlib import Path

_MAIN_DIR = Path(__file__).resolve().parent      # fsdeploy/
_REPO_DIR = _MAIN_DIR.parent                      # ~/fsdeploy/
_LIB_DIR = _REPO_DIR / "lib"                      # ~/fsdeploy/lib/

if _LIB_DIR.is_dir() and str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))

# ═════════════════════════════════════════════════════════════════════════════
# IMPORTS
# ═════════════════════════════════════════════════════════════════════════════

from typing import Optional
import typer


# ═════════════════════════════════════════════════════════════════════════════
# APP TYPER
# ═════════════════════════════════════════════════════════════════════════════

app = typer.Typer(
    name="fsdeploy",
    help="Déploiement et gestion ZFS/ZFSBootMenu depuis Debian Live.",
    no_args_is_help=False,
    add_completion=False,
    pretty_exceptions_enable=False,
)


# ═════════════════════════════════════════════════════════════════════════════
# ÉTAT GLOBAL
# ═════════════════════════════════════════════════════════════════════════════

class GlobalState:
    def __init__(self):
        self.config = None
        self.config_path = None
        self.verbose = False
        self.debug = False
        self.dry_run = False
        self.quiet = False
        self.bypass = False
        self.log_level = "info"


state = GlobalState()


def _load_config(config_path: str | None = None):
    """Charge la configuration configobj."""
    from config import FsDeployConfig

    if config_path:
        state.config = FsDeployConfig(config_path)
        state.config_path = config_path
    elif os.environ.get("FSDEPLOY_CONFIG"):
        state.config = FsDeployConfig(os.environ["FSDEPLOY_CONFIG"])
    else:
        try:
            state.config = FsDeployConfig.default(create=True)
        except Exception:
            state.config = None

    # Overrides CLI → config
    if state.config:
        if state.verbose:
            state.config.set("env.verbose", True)
        if state.debug:
            state.config.set("env.debug", True)
        if state.dry_run:
            state.config.set("env.dry_run", True)
        if state.quiet:
            state.config.set("env.quiet", True)
        if state.bypass:
            state.config.set("env.bypass", True)
        if state.log_level != "info":
            state.config.set("log.level", state.log_level)


def _setup_logging():
    """Configure le logging structlog."""
    log_dir = ""
    if state.config:
        log_dir = state.config.get("log.dir", "")
    try:
        from log import setup_logging
        setup_logging(
            level=state.log_level,
            verbose=state.verbose,
            debug=state.debug,
            quiet=state.quiet,
            log_dir=log_dir,
        )
    except ImportError:
        import logging
        level = getattr(logging, state.log_level.upper(), logging.INFO)
        logging.basicConfig(level=level, format="%(levelname)s: %(message)s")


def _health_check() -> bool:
    """
    Vérifie les prérequis système avant de lancer le daemon.
    Retourne True si tout est ok, False sinon.
    """
    import shutil
    import subprocess
    errors = []
    # Vérifier que zfs est disponible
    if shutil.which("zfs") is None:
        errors.append("zfs command not found")
    # Vérifier que mount est disponible
    if shutil.which("mount") is None:
        errors.append("mount command not found")
    # Vérifier que /proc/mounts est accessible
    try:
        with open("/proc/mounts", "r"):
            pass
    except PermissionError:
        errors.append("cannot read /proc/mounts")
    # Vérifier que le système a au moins 128 MB RAM (approximatif)
    try:
        with open("/proc/meminfo", "r") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    kb = int(line.split()[1])
                    if kb < 128 * 1024:
                        errors.append("system memory below 128 MB")
                    break
    except Exception:
        pass  # ignorer
    if errors:
        from log import get_logger
        logger = get_logger()
        for err in errors:
            logger.warning("Health check: %s", err)
        return False
    return True

def _build_daemon_config() -> dict:
    """Construit le dict de config pour FsDeployDaemon."""
    cfg = {}
    
    if state.config:
        cfg = {
            "env": {
                "verbose": state.config.get("env.verbose", state.verbose),
                "debug": state.config.get("env.debug", state.debug),
                "dry_run": state.config.get("env.dry_run", state.dry_run),
                "quiet": state.config.get("env.quiet", state.quiet),
                "bypass": state.config.get("env.bypass", state.bypass),
            },
            "scheduler": {
                "max_workers": state.config.get("scheduler.max_workers", 4),
                "tick_interval": state.config.get("scheduler.tick_interval", 0.1),
                "bus_udev": state.config.get("scheduler.bus_udev", True),
                "bus_inotify": state.config.get("scheduler.bus_inotify", True),
                "bus_socket": state.config.get("scheduler.bus_socket", True),
                "socket_path": state.config.get("scheduler.socket_path", "/run/fsdeploy.sock"),
            },
            "tui": {
                "enabled": state.config.get("tui.enabled", True),
                "web_port": state.config.get("tui.web_port", 0),
                "auto_restart": state.config.get("tui.auto_restart", True),
                "max_backoff": state.config.get("tui.max_backoff", 60),
            },
            "stream": {
                "youtube_key": state.config.get("stream.youtube_key", ""),
                "resolution": state.config.get("stream.resolution", "1920x1080"),
                "fps": state.config.get("stream.fps", 30),
            },
            "log": {
                "level": state.config.get("log.level", state.log_level),
                "dir": state.config.get("log.dir", ""),
            },
        }
    else:
        cfg = {
            "env": {
                "verbose": state.verbose,
                "debug": state.debug,
                "dry_run": state.dry_run,
                "quiet": state.quiet,
                "bypass": state.bypass,
            },
            "scheduler": {"max_workers": 4},
            "tui": {"enabled": True, "web_port": 0},
            "log": {"level": state.log_level},
        }
    
    return cfg


def _run_daemon(mode: str, web_port: int = 0) -> None:
    """Instancie et lance le FsDeployDaemon."""
    from daemon import FsDeployDaemon

    cfg = _build_daemon_config()
    
    if web_port > 0:
        cfg["tui"]["web_port"] = web_port

    daemon = FsDeployDaemon(config=cfg)

    try:
        daemon.run(mode=mode)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        if state.debug:
            import traceback
            traceback.print_exc()
        else:
            typer.echo(f"Erreur fatale : {e}", err=True)
        raise typer.Exit(1)


# ═════════════════════════════════════════════════════════════════════════════
# CALLBACK PRINCIPAL
# ═════════════════════════════════════════════════════════════════════════════

@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    daemon: bool = typer.Option(False, "--daemon", "-d", help="Mode daemon."),
    bare: bool = typer.Option(False, "--bare", help="Mode bare (pas de TUI)."),
    mode: str = typer.Option("tui", "--mode", "-m", help="Mode: tui, daemon, stream, bare."),
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Chemin config."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Logs verbeux."),
    debug: bool = typer.Option(False, "--debug", help="Mode debug."),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Simulation."),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Logs minimaux."),
    bypass: bool = typer.Option(False, "--bypass", help="Bypass sécurité."),
    log_level: str = typer.Option("info", "--log-level", "-l", help="Niveau log."),
    web_port: int = typer.Option(0, "--web-port", "-w", help="Port textual-web."),
    version: bool = typer.Option(False, "--version", "-V", help="Version."),
):
    """Déploiement et gestion ZFS/ZFSBootMenu."""
    if version:
        print("fsdeploy 0.1.0")
        raise typer.Exit(0)

    state.verbose = verbose
    state.debug = debug
    state.dry_run = dry_run
    state.quiet = quiet
    state.bypass = bypass
    state.log_level = log_level

    _load_config(config)
    _setup_logging()

    if ctx.invoked_subcommand is not None:
        return

    # Déterminer le mode
    if daemon:
        mode = "daemon"
    elif bare:
        mode = "bare"

    # Health check
    if not _health_check():
        from log import get_logger
        logger = get_logger()
        logger.warning("Health check a échoué, continuation malgré tout.")

    _run_daemon(mode=mode, web_port=web_port)


# ═════════════════════════════════════════════════════════════════════════════
# SOUS-COMMANDES
# ═════════════════════════════════════════════════════════════════════════════

@app.command()
def detect(
    pool: Optional[str] = typer.Option(None, "--pool", "-p", help="Pool spécifique."),
    json_output: bool = typer.Option(False, "--json", "-j", help="Sortie JSON."),
):
    """Détecte les pools, datasets et partitions."""
    _load_config(None)
    _setup_logging()
    
    from function.detect.environment import EnvironmentDetectTask
    
    task = EnvironmentDetectTask(id="cli_detect", params={"pool": pool})
    result = task.run()
    
    if json_output:
        import json
        print(json.dumps(result.__dict__, indent=2, default=str))
    else:
        print(f"\nMode: {result.mode}")
        print(f"Init: {result.init_system}")
        print(f"Arch: {result.arch}")
        print(f"RAM: {result.ram_mb} MB")
        print(f"Network: {'yes' if result.network_available else 'no'}")
        print()


@app.command()
def status():
    """Affiche le statut du scheduler."""
    socket_path = "/run/fsdeploy.sock"
    
    if Path(socket_path).exists():
        import socket
        import json
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(socket_path)
            sock.sendall(b'{"action": "status"}\n')
            data = sock.recv(4096)
            sock.close()
            status_data = json.loads(data.decode())
            print(f"Mode: {status_data.get('mode', '?')}")
            print(f"Running: {status_data.get('running_tasks', 0)}")
        except Exception as e:
            print(f"Erreur: {e}", file=sys.stderr)
            raise typer.Exit(1)
    else:
        print("Daemon non actif")
        raise typer.Exit(1)


@app.command()
def coherence(
    fix: bool = typer.Option(False, "--fix", "-f", help="Corriger."),
):
    """Vérifie la cohérence du système."""
    _load_config(None)
    _setup_logging()
    
    from function.coherence.check import CoherenceCheckTask
    
    task = CoherenceCheckTask(id="cli_coherence", params={"auto_fix": fix})
    result = task.run()
    
    print(f"Statut: {result.status}")
    for issue in result.issues:
        print(f"  [{issue.severity}] {issue.message}")


@app.command()
def recovery(
    auto_fix: bool = typer.Option(False, "--fix", "-f", help="Appliquer les corrections."),
    pool: Optional[str] = typer.Option(None, "--pool", "-p"),
):
    """Diagnostic et réparation du système."""
    _load_config(None)
    _setup_logging()

    from function.recovery.diagnose import RecoveryDiagnoseTask

    task = RecoveryDiagnoseTask(auto_fix=auto_fix, pool=pool)
    result = task.run()

    import json
    print(json.dumps(result.output, indent=2, default=str))
    if not result.success:
        raise typer.Exit(1)


@app.command()
def toolchains():
    """Liste les toolchains disponibles."""
    try:
        from function.kernel.crosscompile import ARCHITECTURES, get_available_toolchains
        available = get_available_toolchains()
        print("\n=== Toolchains ===\n")
        for arch in ARCHITECTURES:
            s = "✓" if arch.name in available else "✗"
            print(f"  {s} {arch.name:12} {arch.triplet}")
        print(f"\nDisponibles: {len(available)}/{len(ARCHITECTURES)}\n")
    except ImportError as e:
        print(f"Erreur: {e}", file=sys.stderr)
        raise typer.Exit(1)


# ═════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app()
