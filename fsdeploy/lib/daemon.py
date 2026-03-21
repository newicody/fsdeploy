"""
fsdeploy.daemon
================
Processus racine de fsdeploy.

Architecture :
  - Le daemon/scheduler est le processus racine
  - La TUI Textual est un enfant optionnel et jetable
  - Si Textual crash, le scheduler continue
  - Mode bare = rien lance (scheduler seul)

Connecte tout :
  - Config (configobj) → parametres de tous les composants
  - HuffmanStore → BDD compacte du runtime
  - Scheduler (non-bloquant, ThreadPoolExecutor)
  - Bus (Timer, Inotify, Udev, Socket)
  - Intents (tous importes au boot pour @register_intent)
  - TUI Textual (processus enfant avec restart auto)

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
from scheduler.intentlog.codec import HuffmanStore
from scheduler.model.event import CLIEvent

from bus import TimerSource, InotifySource, UdevSource, SocketSource


class FsDeployDaemon:
    """
    Processus racine.

    Responsabilites :
      - Charger la configuration
      - Instancier le HuffmanStore
      - Demarrer le scheduler (non-bloquant)
      - Demarrer les sources d'evenements (bus)
      - Enregistrer les handlers d'intents
      - Demarrer la TUI (optionnel, processus enfant)
      - Gerer le restart de la TUI avec backoff
      - Arret propre sur SIGTERM/SIGINT
    """

    def __init__(self, config: dict | None = None):
        self.config = config or {}

        # ── HuffmanStore ──────────────────────────────────────────
        self.store = HuffmanStore(
            rebuild_threshold=self.config.get("store_rebuild_threshold", 256),
        )

        # ── Runtime ───────────────────────────────────────────────
        self.runtime = Runtime()
        self.runtime.dry_run = self.config.get("dry_run", False)
        self.runtime.verbose = self.config.get("verbose", False)
        self.runtime.bypass = self.config.get("bypass", False)

        # ── Monitor ───────────────────────────────────────────────
        self.monitor = RuntimeMonitor()

        # ── IntentLog ─────────────────────────────────────────────
        log_dir = self.config.get("log_dir", "")
        if not log_dir:
            install_dir = os.environ.get("FSDEPLOY_INSTALL_DIR", "/opt/fsdeploy")
            log_dir = str(Path(install_dir) / "var" / "log" / "fsdeploy")
        self.intent_log = IntentLog(log_dir=log_dir)

        # ── Security ──────────────────────────────────────────────
        configobj = self.config.get("configobj")
        self.security = SecurityResolver(
            bypass=self.runtime.bypass,
            config=configobj,
        )

        # ── Resolver + Executor ───────────────────────────────────
        max_workers = self.config.get("max_workers", 4)
        self.resolver = Resolver(security_resolver=self.security)
        self.executor = Executor(self.runtime, max_workers=max_workers)

        # ── Scheduler ─────────────────────────────────────────────
        self.scheduler = Scheduler(
            resolver=self.resolver,
            executor=self.executor,
            runtime=self.runtime,
        )
        tick = self.config.get("tick_interval", 0.1)
        self.scheduler._tick_interval = tick

        # ── Bus sources ───────────────────────────────────────────
        self._sources: list = []
        self._tui_process: Optional[subprocess.Popen] = None
        self._tui_backoff = 1
        self._tui_max_backoff = self.config.get("tui_max_backoff", 60)
        self._running = False

    # ═══════════════════════════════════════════════════════════════
    # SETUP
    # ═══════════════════════════════════════════════════════════════

    def _register_all_intents(self) -> None:
        """
        Importe tous les fichiers d'intents pour que les
        @register_intent s'enregistrent dans INTENT_REGISTRY.

        Doit etre appele AVANT le premier cycle du scheduler.
        """
        intent_modules = [
            "intents.boot_intent",
            "intents.detection_intent",
            "intents.kernel_intent",
            "intents.system_intent",
            "intents.test_intent",
        ]
        for mod_name in intent_modules:
            try:
                __import__(mod_name)
            except ImportError:
                pass  # module pas encore cree — pas bloquant

    def _setup_bus(self) -> None:
        """Configure les sources d'evenements."""
        eq = self.runtime.event_queue

        # Timer jobs
        timer = TimerSource(eq)
        timer_jobs = self.config.get("timer_jobs", {})
        if isinstance(timer_jobs, dict):
            for job_name, interval in timer_jobs.items():
                interval = int(interval) if interval else 0
                if interval > 0:
                    timer.add_job(job_name, interval)
        else:
            # Defauts si pas configure
            timer.add_job("coherence_check", 3600)
            timer.add_job("scrub_check", 604800)
        self._sources.append(timer)

        # Inotify
        if self.config.get("bus_inotify", True):
            boot_mount = ""
            configobj = self.config.get("configobj")
            if configobj:
                boot_mount = configobj.get("pool.boot_mount", "")
            watch_paths = [boot_mount] if boot_mount else ["/boot"]
            self._sources.append(InotifySource(eq, watch_paths=watch_paths))

        # Udev
        if self.config.get("bus_udev", True):
            self._sources.append(UdevSource(eq))

        # Socket
        if self.config.get("bus_socket", True):
            socket_path = self.config.get("socket_path", "/run/fsdeploy.sock")
            self._sources.append(SocketSource(eq, socket_path=socket_path))

    def _setup_scheduler_hooks(self) -> None:
        """Hooks pour logger dans le HuffmanStore a chaque cycle."""

        def on_cycle_end(sched):
            # Log les tasks completees dans le store
            with self.runtime.state._lock:
                for task_id, entry in list(self.runtime.state.completed.items()):
                    task = entry.get("task")
                    if task:
                        self.store.log_task(
                            task_id, "completed",
                            task_class=task.__class__.__name__,
                            duration=f"{entry.get('duration', 0):.3f}s",
                        )

                for task_id, entry in list(self.runtime.state.failed.items()):
                    task = entry.get("task")
                    if task:
                        self.store.log_task(
                            task_id, "failed",
                            task_class=task.__class__.__name__,
                            error=str(entry.get("error", "")),
                        )

        self.scheduler.on_cycle_end(on_cycle_end)

    # ═══════════════════════════════════════════════════════════════
    # TUI
    # ═══════════════════════════════════════════════════════════════

    def _start_tui(self) -> None:
        """Demarre la TUI Textual dans un processus enfant."""
        try:
            from ui.app import FsDeployApp

            configobj = self.config.get("configobj")
            mode = "deploy"
            if configobj:
                mode = configobj.get("env.mode", "deploy")

            # La TUI tourne dans le meme processus (thread Textual)
            # car elle a besoin d'acceder au runtime et au store
            self._tui_thread = threading.Thread(
                target=self._run_tui,
                args=(configobj, mode),
                daemon=True,
            )
            self._tui_thread.start()

        except ImportError:
            # Textual pas installe — mode daemon
            pass

    def _run_tui(self, configobj, mode: str) -> None:
        """Execute la TUI dans un thread dedie."""
        try:
            from ui.app import FsDeployApp

            app = FsDeployApp(
                runtime=self.runtime,
                store=self.store,
                config=configobj,
                mode=mode,
            )
            app.run()
        except Exception:
            pass

    def _monitor_tui(self) -> None:
        """Surveille le thread TUI et le redemarre si necessaire."""
        while self._running:
            if hasattr(self, "_tui_thread") and self._tui_thread is not None:
                if not self._tui_thread.is_alive():
                    auto_restart = self.config.get("tui_auto_restart", True)
                    if auto_restart and self._running:
                        time.sleep(self._tui_backoff)
                        self._tui_backoff = min(
                            self._tui_backoff * 2,
                            self._tui_max_backoff,
                        )
                        self._start_tui()
                    else:
                        break
                else:
                    self._tui_backoff = 1
            time.sleep(2)

    # ═══════════════════════════════════════════════════════════════
    # MAIN
    # ═══════════════════════════════════════════════════════════════

    def run(self, mode: str = "tui") -> None:
        """
        Point d'entree principal.

        Modes :
          tui    : scheduler + TUI
          daemon : scheduler seul (service)
          stream : scheduler + stream YouTube
          bare   : scheduler seul, pas de TUI
        """
        self._running = True

        # 1. Enregistrer tous les intents
        self._register_all_intents()

        # 2. Setup bus
        self._setup_bus()

        # 3. Hooks scheduler → store
        self._setup_scheduler_hooks()

        # 4. Demarrer les sources
        for source in self._sources:
            source.start()

        # 5. Mode stream
        if mode == "stream":
            configobj = self.config.get("configobj")
            stream_key = self.config.get("stream_key", "")
            if not stream_key and configobj:
                stream_key = configobj.get("stream.youtube_key", "")
            self.runtime.event_queue.put(CLIEvent(
                command="stream_start",
                args={
                    "stream_key": stream_key,
                    "resolution": self.config.get("resolution", "1920x1080"),
                    "fps": self.config.get("fps", 30),
                },
            ))

        # 6. TUI
        tui_monitor = None
        tui_enabled = self.config.get("tui_enabled", True)
        if mode == "tui" and tui_enabled:
            self._start_tui()
            tui_monitor = threading.Thread(
                target=self._monitor_tui, daemon=True)
            tui_monitor.start()

        # 7. Log demarrage
        self.store.log_event("daemon.started", source="daemon",
                             mode=mode, pid=str(os.getpid()))

        # 8. Boucle principale du scheduler (bloquante)
        try:
            self.scheduler.run()
        except KeyboardInterrupt:
            pass
        finally:
            self._shutdown()

    def _shutdown(self) -> None:
        """Arret propre de tous les composants."""
        self._running = False
        self.scheduler.stop()

        # Arreter l'executor (attend les tasks threaded)
        self.executor.shutdown(wait=True, timeout=30)

        # Arreter les sources
        for source in self._sources:
            source.stop()

        # Sauvegarder le store
        store_path = Path(
            os.environ.get("FSDEPLOY_INSTALL_DIR", "/opt/fsdeploy")
        ) / "var" / "lib" / "fsdeploy" / "runtime.hfdb"
        try:
            store_path.parent.mkdir(parents=True, exist_ok=True)
            self.store.save(store_path)
        except Exception:
            pass

        self.store.log_event("daemon.stopped", source="daemon")
