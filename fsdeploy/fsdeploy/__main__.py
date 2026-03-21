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

import os
import sys
from pathlib import Path
from typing import Optional

import typer

import fsdeploy


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
      3. FsDeployConfig.default() (recherche automatique)
    """
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
            # Pas de config trouvée — on continue avec les défauts CLI
            state.config = None

    # Appliquer les overrides CLI → config
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
    """Configure structlog selon les options."""
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
        help="Mode daemon (scheduler seul, pas de TUI)."),
    bare: bool = typer.Option(
        False, "--bare",
        help="Mode bare (scheduler seul, pas de TUI ni stream)."),
    mode: Optional[str] = typer.Option(
        None, "--mode", "-m",
        help="Mode d'exécution : tui | daemon | stream | bare."),

    # Flags globaux
    verbose: bool = typer.Option(
        False, "--verbose", "-v",
        help="Affiche toutes les commandes et sorties."),
    debug: bool = typer.Option(
        False, "--debug",
        help="Dump complet config + traces internes."),
    dry_run: bool = typer.Option(
        False, "--dry-run", "-n",
        help="Simule sans rien modifier."),
    quiet: bool = typer.Option(
        False, "--quiet", "-q",
        help="Erreurs uniquement."),
    bypass: bool = typer.Option(
        False, "--bypass",
        help="Désactive toutes les vérifications de sécurité."),

    # Config
    config: Optional[str] = typer.Option(
        None, "--config", "-c",
        help="Chemin vers fsdeploy.conf."),
    log_level: str = typer.Option(
        "info", "--log-level",
        help="Niveau de log : debug | info | warning | error."),

    # Stream raccourci
    stream_key: Optional[str] = typer.Option(
        None, "--stream-key",
        help="Clé YouTube pour le mode stream."),

    # Pool raccourci
    pool: Optional[list[str]] = typer.Option(
        None, "--pool",
        help="Pools à importer (répétable)."),

    # Version
    version: bool = typer.Option(
        False, "--version", "-V",
        help="Affiche la version et quitte."),
):
    """
    fsdeploy — Déploiement et gestion ZFS/ZFSBootMenu.

    Sans sous-commande : lance le daemon + TUI interactive.
    Avec --daemon ou --bare : lance le scheduler sans TUI.
    Avec --mode stream : lance le scheduler + stream YouTube.
    """
    # Version
    if version:
        typer.echo(f"fsdeploy {fsdeploy.__version__}")
        raise typer.Exit()

    # Stocker l'état global
    state.verbose = verbose
    state.debug = debug
    state.dry_run = dry_run
    state.quiet = quiet
    state.bypass = bypass
    state.log_level = log_level

    # Si une sous-commande est invoquée, on laisse typer la dispatcher
    if ctx.invoked_subcommand is not None:
        _load_config(config)
        _setup_logging()
        return

    # ── Pas de sous-commande → lancer le daemon ──────────────────────────

    # Résoudre le mode
    if mode:
        run_mode = mode
    elif daemon:
        run_mode = "daemon"
    elif bare:
        run_mode = "bare"
    else:
        run_mode = "tui"

    # Config
    _load_config(config)
    _setup_logging()

    # Override stream key si fourni en CLI
    if stream_key and state.config:
        state.config.set("stream.youtube_key", stream_key)
        if run_mode == "tui":
            run_mode = "stream"

    # Override pools si fournis en CLI
    if pool and state.config:
        for i, p in enumerate(pool):
            key = ["boot_pool", "fast_pool", "data_pool"][i] if i < 3 else f"pool_{i}"
            state.config.set(f"pool.{key}", p)

    # Bannière
    if not quiet:
        _print_banner(run_mode)

    # Debug dump
    if debug and state.config:
        _debug_dump()

    # Lancer le daemon
    _run_daemon(run_mode)


# ═════════════════════════════════════════════════════════════════════════════
# SOUS-COMMANDES CLI
# ═════════════════════════════════════════════════════════════════════════════

@app.command()
def detect(
    pool: Optional[list[str]] = typer.Option(
        None, "--pool", "-p",
        help="Pools à scanner (répétable)."),
    import_missing: bool = typer.Option(
        False, "--import-missing",
        help="Importer les pools non importés."),
    readonly: bool = typer.Option(
        True, "--readonly/--no-readonly",
        help="Importer en lecture seule."),
    json_output: bool = typer.Option(
        False, "--json",
        help="Sortie JSON."),
):
    """Détecte les pools, datasets et partitions."""
    _load_config(state.config_path)
    _setup_logging()

    from function.detect.environment import EnvironmentDetectTask

    task = EnvironmentDetectTask(id="cli_detect", params={
        "pools": pool or [],
        "import_missing": import_missing,
        "readonly": readonly,
    })

    result = task.run()

    if json_output:
        import json
        typer.echo(json.dumps({
            "mode": result.mode,
            "init_system": result.init_system,
            "arch": result.arch,
            "cpu": result.cpu_model,
            "ram_mb": result.ram_mb,
            "network": result.network_available,
            "framebuffer": result.is_framebuffer,
        }, indent=2))
    else:
        typer.echo(f"Mode        : {result.mode}")
        typer.echo(f"Init system : {result.init_system}")
        typer.echo(f"Arch        : {result.arch}")
        typer.echo(f"CPU         : {result.cpu_model}")
        typer.echo(f"RAM         : {result.ram_mb} MB")
        typer.echo(f"Network     : {'oui' if result.network_available else 'non'}")
        typer.echo(f"Framebuffer : {'oui' if result.is_framebuffer else 'non'}")


@app.command()
def snapshot(
    action: str = typer.Argument(
        ..., help="Action : create | list | rollback | send"),
    dataset: Optional[str] = typer.Option(
        None, "--dataset", "-d",
        help="Dataset cible."),
    name: Optional[str] = typer.Option(
        None, "--name", "-n",
        help="Nom du snapshot (auto-généré si omis)."),
    recursive: bool = typer.Option(
        False, "--recursive", "-r",
        help="Snapshot récursif."),
):
    """Gestion des snapshots ZFS."""
    _load_config(state.config_path)
    _setup_logging()

    if action == "create":
        from function.snapshot.create import SnapshotCreateTask
        task = SnapshotCreateTask(id="cli_snap", params={
            "dataset": dataset or "",
            "name": name or "",
            "recursive": recursive,
        })
        result = task.run()
        typer.echo(f"Snapshot créé : {result.get('snapshot', '?')}")

    elif action == "list":
        from function.snapshot.create import SnapshotListTask
        task = SnapshotListTask(id="cli_snaplist", params={
            "dataset": dataset or "",
        })
        for snap in task.run():
            typer.echo(f"  {snap.get('name', '?'):50s}  {snap.get('used', '?')}")

    elif action == "rollback":
        from function.snapshot.create import SnapshotRollbackTask
        if not dataset:
            typer.echo("--dataset requis pour rollback", err=True)
            raise typer.Exit(1)
        task = SnapshotRollbackTask(id="cli_rollback", params={
            "snapshot": dataset,
            "confirmed": True,
        })
        result = task.run()
        typer.echo(f"Rollback : {result.get('snapshot', '?')}")

    else:
        typer.echo(f"Action inconnue : {action}", err=True)
        raise typer.Exit(1)


@app.command()
def coherence(
    boot_path: str = typer.Option(
        "/boot", "--boot-path",
        help="Chemin du répertoire de boot."),
    preset: Optional[str] = typer.Option(
        None, "--preset",
        help="Nom du preset à vérifier."),
    json_output: bool = typer.Option(
        False, "--json",
        help="Sortie JSON."),
):
    """Vérifie la cohérence du système avant boot."""
    _load_config(state.config_path)
    _setup_logging()

    from function.coherence.check import CoherenceCheckTask

    # Charger le preset depuis la config si spécifié
    preset_data = {}
    if preset and state.config:
        preset_data = dict(state.config.get(f"presets.{preset}", {}))

    task = CoherenceCheckTask(id="cli_coherence", params={
        "boot_path": boot_path,
        "preset": preset_data,
    })
    report = task.run()

    if json_output:
        import json
        typer.echo(json.dumps({
            "passed": report.passed,
            "summary": report.summary(),
            "checks": [
                {"name": c.name, "passed": c.passed,
                 "message": c.message, "severity": c.severity}
                for c in report.checks
            ],
        }, indent=2))
    else:
        for check in report.checks:
            icon = "✅" if check.passed else ("❌" if check.severity == "error" else "⚠️")
            typer.echo(f"  {icon} {check.name:20s} {check.message}")
        typer.echo(f"\n{report.summary()}")

        if not report.passed:
            raise typer.Exit(1)


@app.command()
def status():
    """Affiche l'état des pools et du scheduler."""
    _load_config(state.config_path)
    _setup_logging()

    from function.pool.status import PoolStatusTask

    task = PoolStatusTask(id="cli_status", params={})
    result = task.run()
    typer.echo(result.get("output", "Aucun pool trouvé."))


# ═════════════════════════════════════════════════════════════════════════════
# LANCEMENT DU DAEMON
# ═════════════════════════════════════════════════════════════════════════════

def _run_daemon(mode: str) -> None:
    """Instancie et lance le FsDeployDaemon."""
    from daemon import FsDeployDaemon

    cfg = _build_daemon_config()
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
# UTILITAIRES
# ═════════════════════════════════════════════════════════════════════════════

def _print_banner(mode: str) -> None:
    """Bannière de démarrage."""
    try:
        from rich.console import Console
        from rich.panel import Panel
        console = Console()
        console.print(Panel.fit(
            f"[bold]fsdeploy[/] v{fsdeploy.__version__}  —  mode [cyan]{mode}[/]",
            border_style="blue",
        ))
    except ImportError:
        print(f"fsdeploy v{fsdeploy.__version__} — mode {mode}")
        print("=" * 50)


def _debug_dump() -> None:
    """Dump de debug : config + environnement."""
    typer.echo("\n── Debug dump ──")
    typer.echo(f"Version    : {fsdeploy.__version__}")
    typer.echo(f"Install dir: {fsdeploy.get_install_dir()}")
    typer.echo(f"Lib dir    : {fsdeploy.get_lib_dir()}")
    typer.echo(f"Python     : {sys.executable}")
    typer.echo(f"sys.path   : {sys.path[:5]}")

    if state.config:
        typer.echo(f"Config path: {state.config.path}")
        typer.echo(f"Mode       : {state.config.get('env.mode', '?')}")
        typer.echo(f"Boot pool  : {state.config.get('pool.boot_pool', '?')}")
        typer.echo(f"Log level  : {state.config.get('log.level', '?')}")

    env_vars = {k: v for k, v in os.environ.items() if k.startswith("FSDEPLOY_")}
    if env_vars:
        typer.echo("Env vars   :")
        for k, v in sorted(env_vars.items()):
            typer.echo(f"  {k}={v}")

    typer.echo("")


# ═════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app()
