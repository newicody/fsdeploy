"""
fsdeploy.__main__
==================
Point d'entrée CLI : python3 -m fsdeploy [OPTIONS] [COMMAND]

Modes d'exécution :
  python3 -m fsdeploy                   # TUI interactive (défaut)
  python3 -m fsdeploy --daemon          # daemon seul (service systemd)
  python3 -m fsdeploy --bare            # scheduler seul, pas de TUI
  python3 -m fsdeploy --mode stream     # scheduler + stream YouTube
  python3 -m fsdeploy detect            # sous-commande CLI directe
  python3 -m fsdeploy snapshot create   # sous-commande CLI directe

Résolution des options (priorité) :
  1. Arguments CLI (--verbose, --config, etc.)
  2. Variables d'environnement ($FSDEPLOY_VERBOSE, etc.)
  3. Fichier fsdeploy.conf (configobj)
  4. Valeurs par défaut du configspec
"""

# ═════════════════════════════════════════════════════════════════════════════
# PATH SETUP — DOIT ÊTRE AVANT TOUT AUTRE IMPORT
# ═════════════════════════════════════════════════════════════════════════════

import os
import sys
from pathlib import Path

# Les modules scheduler/, function/, intents/, bus/, config.py vivent dans lib/.
# On ajoute lib/ au sys.path pour que les imports bare fonctionnent.
_MAIN_DIR = Path(__file__).resolve().parent
_LIB_DIR = _MAIN_DIR / "lib"

if _LIB_DIR.is_dir() and str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))

# ═════════════════════════════════════════════════════════════════════════════
# IMPORTS (maintenant que lib/ est dans le path)
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
# OPTIONS GLOBALES
# ═════════════════════════════════════════════════════════════════════════════

class GlobalState:
    """État global partagé entre les commandes."""

    def __init__(self):
        self.config = None       # FsDeployConfig
        self.config_path = None  # chemin explicite
        self.verbose = False
        self.debug = False
        self.dry_run = False
        self.quiet = False
        self.bypass = False
        self.log_level = "info"


state = GlobalState()


def _load_config(config_path: str | None = None):
    """
    Charge la configuration configobj.

    Ordre de recherche :
      1. --config explicite
      2. $FSDEPLOY_CONFIG
      3. /boot/fsdeploy/fsdeploy.conf (boot_pool monté)
      4. /etc/fsdeploy/fsdeploy.conf
      5. ./fsdeploy.conf (dev)
    """
    from config import FsDeployConfig

    search_paths = []

    # 1. Explicite
    if config_path:
        search_paths.append(Path(config_path))

    # 2. Env
    env_config = os.environ.get("FSDEPLOY_CONFIG")
    if env_config:
        search_paths.append(Path(env_config))

    # 3-5. Chemins standards
    search_paths.extend([
        Path("/boot/fsdeploy/fsdeploy.conf"),
        Path("/etc/fsdeploy/fsdeploy.conf"),
        Path("fsdeploy.conf"),
    ])

    # Chercher le premier existant
    for path in search_paths:
        if path.exists():
            state.config_path = str(path)
            state.config = FsDeployConfig(str(path))
            return

    # Pas de config trouvée — utiliser les défauts
    state.config = FsDeployConfig.default()


def _setup_logging():
    """Configure le logging structlog."""
    try:
        from log import setup_logging
        setup_logging(
            level=state.log_level,
            verbose=state.verbose,
            debug=state.debug,
            quiet=state.quiet,
        )
    except ImportError:
        # log.py pas encore disponible — logging basique
        import logging
        level = getattr(logging, state.log_level.upper(), logging.INFO)
        logging.basicConfig(level=level, format="%(levelname)s: %(message)s")


def _build_daemon_config() -> dict:
    """Construit le dict de config pour FsDeployDaemon."""
    cfg = {}

    if state.config:
        # Flags
        cfg["dry_run"] = state.config.get("env.dry_run", state.dry_run)
        cfg["verbose"] = state.config.get("env.verbose", state.verbose)
        cfg["debug"] = state.config.get("env.debug", state.debug)
        cfg["bypass"] = state.config.get("env.bypass", state.bypass)

        # Scheduler
        cfg["max_workers"] = state.config.get("scheduler.max_workers", 4)
        cfg["tick_interval"] = state.config.get("scheduler.tick_interval", 0.1)

        # Bus
        cfg["bus_udev"] = state.config.get("scheduler.bus_udev", True)
        cfg["bus_inotify"] = state.config.get("scheduler.bus_inotify", True)
        cfg["bus_socket"] = state.config.get("scheduler.bus_socket", True)
        cfg["socket_path"] = state.config.get("scheduler.socket_path",
                                               "/run/fsdeploy.sock")

        # TUI
        cfg["tui_enabled"] = state.config.get("tui.enabled", True)
        cfg["tui_web_port"] = state.config.get("tui.web_port", 0)
        cfg["tui_auto_restart"] = state.config.get("tui.auto_restart", True)
        cfg["tui_max_backoff"] = state.config.get("tui.max_backoff", 60)

        # Stream
        cfg["stream_key"] = state.config.get("stream.youtube_key", "")
        cfg["resolution"] = state.config.get("stream.resolution", "1920x1080")
        cfg["fps"] = state.config.get("stream.fps", 30)
        cfg["start_delay"] = state.config.get("stream.start_delay", 30)

        # Logging
        cfg["log_level"] = state.config.get("log.level", state.log_level)
        cfg["log_dir"] = state.config.get("log.dir", "")

        # Timer jobs
        timer_jobs = state.config.get("scheduler.timer_jobs", {})
        if isinstance(timer_jobs, dict):
            cfg["timer_jobs"] = timer_jobs

        # Configobj complet pour le SecurityResolver
        cfg["configobj"] = state.config

    else:
        # Pas de config — défauts CLI
        cfg["dry_run"] = state.dry_run
        cfg["verbose"] = state.verbose
        cfg["debug"] = state.debug
        cfg["bypass"] = state.bypass
        cfg["max_workers"] = 4
        cfg["tui_enabled"] = True
        cfg["log_level"] = state.log_level

    return cfg


# ═════════════════════════════════════════════════════════════════════════════
# CALLBACK PRINCIPAL (options globales)
# ═════════════════════════════════════════════════════════════════════════════

@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,

    # Mode
    daemon: bool = typer.Option(
        False, "--daemon", "-d",
        help="Mode daemon (scheduler seul, pas de TUI)."
    ),
    bare: bool = typer.Option(
        False, "--bare",
        help="Mode bare (scheduler seul, pas de TUI ni bus)."
    ),
    mode: str = typer.Option(
        "tui", "--mode", "-m",
        help="Mode d'exécution : tui, daemon, stream, bare."
    ),

    # Config
    config: Optional[str] = typer.Option(
        None, "--config", "-c",
        help="Chemin vers fsdeploy.conf."
    ),

    # Flags
    verbose: bool = typer.Option(
        False, "--verbose", "-v",
        help="Logs verbeux."
    ),
    debug: bool = typer.Option(
        False, "--debug",
        help="Mode debug (traces complètes)."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", "-n",
        help="Simulation sans modifications."
    ),
    quiet: bool = typer.Option(
        False, "--quiet", "-q",
        help="Logs minimaux."
    ),
    bypass: bool = typer.Option(
        False, "--bypass",
        help="Bypass les vérifications de sécurité."
    ),
    log_level: str = typer.Option(
        "info", "--log-level", "-l",
        help="Niveau de log : debug, info, warning, error."
    ),

    # TUI
    web_port: int = typer.Option(
        0, "--web-port", "-w",
        help="Port pour textual-web (0 = désactivé)."
    ),

    # Version
    version: bool = typer.Option(
        False, "--version", "-V",
        help="Afficher la version."
    ),
):
    """
    Déploiement et gestion ZFS/ZFSBootMenu.

    Sans commande : lance la TUI interactive.
    Avec --daemon : lance le scheduler en arrière-plan.
    """
    # Version
    if version:
        print(f"fsdeploy 0.1.0")
        raise typer.Exit(0)

    # Stocker les options globales
    state.verbose = verbose
    state.debug = debug
    state.dry_run = dry_run
    state.quiet = quiet
    state.bypass = bypass
    state.log_level = log_level

    # Charger la config
    _load_config(config)

    # Setup logging
    _setup_logging()

    # Si une sous-commande est appelée, on s'arrête là
    if ctx.invoked_subcommand is not None:
        return

    # Déterminer le mode
    if daemon:
        mode = "daemon"
    elif bare:
        mode = "bare"

    # Lancer le daemon avec le mode approprié
    from daemon import FsDeployDaemon

    daemon_config = _build_daemon_config()
    daemon_config["mode"] = mode

    if web_port > 0:
        daemon_config["tui_web_port"] = web_port

    d = FsDeployDaemon(**daemon_config)

    try:
        d.start()
    except KeyboardInterrupt:
        d.stop()


# ═════════════════════════════════════════════════════════════════════════════
# SOUS-COMMANDES
# ═════════════════════════════════════════════════════════════════════════════

@app.command()
def detect(
    pool: Optional[str] = typer.Option(None, "--pool", "-p", help="Pool spécifique."),
    json_output: bool = typer.Option(False, "--json", "-j", help="Sortie JSON."),
):
    """Détecte les pools, datasets et partitions."""
    from daemon import FsDeployDaemon

    daemon_config = _build_daemon_config()
    daemon_config["mode"] = "bare"
    daemon_config["tui_enabled"] = False

    d = FsDeployDaemon(**daemon_config)
    d.start_scheduler_only()

    # Émettre l'event de détection
    d.emit("detection.start", pool=pool)

    # Attendre le résultat
    import time
    timeout = 30
    start = time.time()

    while time.time() - start < timeout:
        result = d.poll_completed("detection.start")
        if result:
            if json_output:
                import json
                print(json.dumps(result, indent=2, default=str))
            else:
                _print_detection_result(result)
            break
        time.sleep(0.1)
    else:
        print("Timeout: détection non terminée", file=sys.stderr)
        raise typer.Exit(1)

    d.stop()


def _print_detection_result(result: dict):
    """Affiche le résultat de détection en texte."""
    print("\n=== Détection fsdeploy ===\n")

    pools = result.get("pools", [])
    if pools:
        print(f"Pools ZFS ({len(pools)}):")
        for p in pools:
            print(f"  • {p['name']} ({p['state']})")

    datasets = result.get("datasets", [])
    if datasets:
        print(f"\nDatasets ({len(datasets)}):")
        for ds in datasets:
            role = ds.get("role", "unknown")
            print(f"  • {ds['name']} [{role}]")

    partitions = result.get("partitions", [])
    if partitions:
        print(f"\nPartitions boot ({len(partitions)}):")
        for p in partitions:
            print(f"  • {p['device']} ({p.get('fstype', '?')})")

    print()


@app.command()
def snapshot(
    action: str = typer.Argument(..., help="Action: list, create, rollback, send."),
    dataset: Optional[str] = typer.Option(None, "--dataset", "-d", help="Dataset cible."),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Nom du snapshot."),
    target: Optional[str] = typer.Option(None, "--target", "-t", help="Cible pour send."),
):
    """Gère les snapshots ZFS."""
    from daemon import FsDeployDaemon

    daemon_config = _build_daemon_config()
    daemon_config["mode"] = "bare"
    daemon_config["tui_enabled"] = False

    d = FsDeployDaemon(**daemon_config)
    d.start_scheduler_only()

    event_name = f"snapshot.{action}"
    params = {}

    if dataset:
        params["dataset"] = dataset
    if name:
        params["name"] = name
    if target:
        params["target"] = target

    d.emit(event_name, **params)

    # Attendre le résultat
    import time
    timeout = 60
    start = time.time()

    while time.time() - start < timeout:
        result = d.poll_completed(event_name)
        if result is not None:
            if isinstance(result, list):
                for snap in result:
                    print(snap)
            else:
                print(result)
            break
        time.sleep(0.1)
    else:
        print(f"Timeout: {action} non terminé", file=sys.stderr)
        raise typer.Exit(1)

    d.stop()


@app.command()
def coherence(
    fix: bool = typer.Option(False, "--fix", "-f", help="Corriger les problèmes."),
    json_output: bool = typer.Option(False, "--json", "-j", help="Sortie JSON."),
):
    """Vérifie la cohérence du système."""
    from daemon import FsDeployDaemon

    daemon_config = _build_daemon_config()
    daemon_config["mode"] = "bare"
    daemon_config["tui_enabled"] = False

    d = FsDeployDaemon(**daemon_config)
    d.start_scheduler_only()

    d.emit("coherence.check", auto_fix=fix)

    import time
    timeout = 60
    start = time.time()

    while time.time() - start < timeout:
        result = d.poll_completed("coherence.check")
        if result:
            if json_output:
                import json
                print(json.dumps(result, indent=2, default=str))
            else:
                _print_coherence_result(result)
            break
        time.sleep(0.1)
    else:
        print("Timeout: vérification non terminée", file=sys.stderr)
        raise typer.Exit(1)

    d.stop()


def _print_coherence_result(result: dict):
    """Affiche le résultat de cohérence."""
    print("\n=== Cohérence système ===\n")

    status = result.get("status", "unknown")
    print(f"Statut: {status}")

    issues = result.get("issues", [])
    if issues:
        print(f"\nProblèmes ({len(issues)}):")
        for issue in issues:
            severity = issue.get("severity", "info")
            msg = issue.get("message", "?")
            print(f"  [{severity}] {msg}")
    else:
        print("\nAucun problème détecté.")

    print()


@app.command()
def status():
    """Affiche le statut du scheduler."""
    from daemon import FsDeployDaemon

    daemon_config = _build_daemon_config()
    daemon_config["mode"] = "bare"
    daemon_config["tui_enabled"] = False

    d = FsDeployDaemon(**daemon_config)

    # Essayer de se connecter au socket
    socket_path = daemon_config.get("socket_path", "/run/fsdeploy.sock")

    if Path(socket_path).exists():
        # Daemon actif
        import socket
        import json

        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(socket_path)
            sock.sendall(b'{"action": "status"}\n')
            data = sock.recv(4096)
            sock.close()

            status_data = json.loads(data.decode())
            print("\n=== fsdeploy status ===\n")
            print(f"Mode: {status_data.get('mode', '?')}")
            print(f"Uptime: {status_data.get('uptime', '?')}")
            print(f"Tasks running: {status_data.get('running_tasks', 0)}")
            print(f"Tasks completed: {status_data.get('completed_tasks', 0)}")
            print()

        except Exception as e:
            print(f"Erreur connexion socket: {e}", file=sys.stderr)
            raise typer.Exit(1)
    else:
        print("fsdeploy daemon non actif (socket introuvable)")
        raise typer.Exit(1)


@app.command()
def toolchains():
    """Liste les toolchains de cross-compilation disponibles."""
    try:
        from function.kernel.crosscompile import ARCHITECTURES, get_available_toolchains

        available = get_available_toolchains()

        print("\n=== Toolchains de cross-compilation ===\n")

        for arch in ARCHITECTURES:
            status = "✓" if arch.name in available else "✗"
            print(f"  {status} {arch.name:12} {arch.triplet:30} {arch.description}")

        print(f"\nDisponibles: {len(available)}/{len(ARCHITECTURES)}")
        print()

    except ImportError as e:
        print(f"Module crosscompile non disponible: {e}", file=sys.stderr)
        raise typer.Exit(1)


# ═════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app()
