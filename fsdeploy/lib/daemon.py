"""
fsdeploy.daemon
================
Processus racine de fsdeploy.

Architecture :
  - Le daemon/scheduler est le processus racine
  - La TUI Textual est un enfant optionnel et jetable
  - Si Textual crash, le scheduler continue
  - Mode bare = rien lancé (scheduler seul)

Usage :
  python3 -m fsdeploy                  # TUI interactive
  python3 -m fsdeploy --daemon         # daemon seul (service)
  python3 -m fsdeploy --mode stream    # stream YouTube
  python3 -m fsdeploy --bare           # scheduler sans TUI
"""

import os
import sys
import time
import signal
import threading
import subprocess
from pathlib import Path
from typing import Optional

from scheduler.core.scheduler import Scheduler
from scheduler.core.executor import Executor
from scheduler.core.resolver import Resolver
from scheduler.core.runtime import Runtime
from scheduler.security.resolver import SecurityResolver
from scheduler.runtime.monitor import RuntimeMonitor
from scheduler.intentlog.log import IntentLog
from scheduler.model.event import CLIEvent

from bus import TimerSource, InotifySource, UdevSource, SocketSource


class FsDeployDaemon:
    """
    Processus racine.

    Responsabilités :
      - Démarrer le scheduler
      - Démarrer les sources d'événements (bus)
      - Démarrer la TUI (optionnel, en processus enfant)
      - Gérer le restart de la TUI avec backoff
      - Arrêt propre sur SIGTERM/SIGINT
    """

    def __init__(self, config: dict | None = None):
        self.config = config or {}

        # Runtime
        self.runtime = Runtime()
        self.runtime.dry_run = self.config.get("dry_run", False)
        self.runtime.verbose = self.config.get("verbose", False)
        self.runtime.bypass = self.config.get("bypass", False)

        # Monitor
        self.monitor = RuntimeMonitor()

        # IntentLog
        log_dir = self.config.get("log_dir", "/var/log/fsdeploy")
        self.intent_log = IntentLog(log_dir=log_dir)

        # Security
        self.security = SecurityResolver(
            bypass=self.runtime.bypass,
            config=self.config,
        )

        # Resolver + Executor
        self.resolver = Resolver(security_resolver=self.security)
        self.executor = Executor(self.runtime)

        # Scheduler
        self.scheduler = Scheduler(
            resolver=self.resolver,
            executor=self.executor,
            runtime=self.runtime,
        )

        # Bus sources
        self._sources: list = []
        self._tui_process: Optional[subprocess.Popen] = None
        self._tui_backoff = 1  # secondes, double à chaque crash
        self._tui_max_backoff = 60
        self._running = False

    # ── Setup ─────────────────────────────────────────────────────────────────

    def _setup_bus(self) -> None:
        """Configure les sources d'événements."""

        # Timer : jobs périodiques
        timer = TimerSource(self.runtime.event_queue)

        # Coherence check toutes les heures
        timer.add_job("coherence_check", interval=3600)

        # Snapshots auto toutes les 6h
        auto_snap_datasets = self.config.get("auto_snapshot_datasets", [])
        if auto_snap_datasets:
            timer.add_job("snapshot_auto", interval=21600,
                         params={"datasets": auto_snap_datasets})

        # Scrub hebdomadaire
        scrub_pools = self.config.get("scrub_pools", [])
        if scrub_pools:
            timer.add_job("scrub_check", interval=604800,
                         params={"pools": scrub_pools})

        self._sources.append(timer)

        # Inotify sur /boot
        boot_path = self.config.get("boot_path", "/boot")
        if Path(boot_path).exists():
            inotify = InotifySource(
                self.runtime.event_queue,
                watch_paths=[boot_path],
            )
            self._sources.append(inotify)

        # Udev (optionnel, nécessite pyudev)
        try:
            import pyudev
            udev = UdevSource(self.runtime.event_queue)
            self._sources.append(udev)
        except ImportError:
            pass

        # Socket Unix pour contrôle CLI
        socket_src = SocketSource(self.runtime.event_queue)
        self._sources.append(socket_src)

    def _setup_intent_handlers(self) -> None:
        """Enregistre les handlers event → intent."""
        # Import des intents pour déclencher les @register_intent
        import intents.boot_intent  # noqa: F401

        from scheduler.core.registry import INTENT_REGISTRY

        for event_name, intent_cls in INTENT_REGISTRY.items():
            def make_handler(cls):
                def handler(event):
                    return [cls(
                        params=event.params,
                        context={"role": "admin", "event": event},
                    )]
                return handler

            self.runtime.intent_queue.register_handler(
                event_name, make_handler(intent_cls)
            )

    # ── TUI Management ────────────────────────────────────────────────────────

    def _start_tui(self) -> None:
        """Lance la TUI Textual dans un processus enfant."""
        venv = os.environ.get("FSDEPLOY_VENV", "")
        python = f"{venv}/bin/python3" if venv else sys.executable

        install_dir = os.environ.get("FSDEPLOY_INSTALL_DIR", "/opt/fsdeploy")

        try:
            self._tui_process = subprocess.Popen(
                [python, "-m", "fsdeploy.ui"],
                cwd=install_dir,
                env={**os.environ, "FSDEPLOY_DAEMON_SOCKET": "/run/fsdeploy.sock"},
            )
        except Exception as e:
            self.monitor.log(f"Failed to start TUI: {e}", level="error")
            self._tui_process = None

    def _monitor_tui(self) -> None:
        """Thread qui surveille la TUI et la redémarre si elle crash."""
        while self._running:
            if self._tui_process is not None:
                retcode = self._tui_process.poll()
                if retcode is not None:
                    self.monitor.log(
                        f"TUI exited with code {retcode}, "
                        f"restarting in {self._tui_backoff}s",
                        level="warning",
                    )
                    time.sleep(self._tui_backoff)
                    self._tui_backoff = min(
                        self._tui_backoff * 2,
                        self._tui_max_backoff,
                    )
                    if self._running:
                        self._start_tui()
                else:
                    # TUI running, reset backoff
                    self._tui_backoff = 1
            time.sleep(2)

    # ── Main ──────────────────────────────────────────────────────────────────

    def run(self, mode: str = "tui") -> None:
        """
        Point d'entrée principal.

        Modes :
          - tui    : scheduler + TUI
          - daemon : scheduler seul (service)
          - stream : scheduler + stream YouTube
          - bare   : scheduler seul, pas de TUI
        """
        self._running = True

        # Setup
        self._setup_bus()
        self._setup_intent_handlers()

        # Démarrer les sources
        for source in self._sources:
            source.start()

        # Mode spécifique
        if mode == "stream":
            self.runtime.event_queue.put(CLIEvent(
                command="stream_start",
                args={
                    "stream_key": self.config.get("stream_key", ""),
                    "resolution": self.config.get("resolution", "1920x1080"),
                    "fps": self.config.get("fps", 30),
                },
            ))

        # TUI (optionnel)
        tui_thread = None
        if mode == "tui":
            self._start_tui()
            tui_thread = threading.Thread(target=self._monitor_tui, daemon=True)
            tui_thread.start()

        # Boucle principale du scheduler (bloquante)
        try:
            self.scheduler.run()
        except KeyboardInterrupt:
            pass
        finally:
            self._shutdown()

    def _shutdown(self) -> None:
        """Arrêt propre."""
        self._running = False
        self.scheduler.stop()

        # Arrêter les sources
        for source in self._sources:
            source.stop()

        # Arrêter la TUI
        if self._tui_process and self._tui_process.poll() is None:
            self._tui_process.terminate()
            try:
                self._tui_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._tui_process.kill()

        self.monitor.log("Daemon stopped", level="info")
