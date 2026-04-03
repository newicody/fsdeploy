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
  - TUI Textual (main thread pour signal handlers)

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
      - Demarrer la TUI (main thread — requis par Textual)
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

        # Socket — chemin user-writable si /run echoue
        if self.config.get("bus_socket", True):
            socket_path = self.config.get("socket_path", "")
            if not socket_path:
                socket_path = _resolve_socket_path()
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
    # SCHEDULER (background thread)
    # ═══════════════════════════════════════════════════════════════

    def _run_scheduler_background(self) -> None:
        """
        Execute le scheduler dans un thread background.

        Le scheduler tourne en boucle jusqu'a self._running == False.
        Cela libere le main thread pour Textual (qui a besoin des
        signal handlers POSIX — SIGTSTP, SIGWINCH, etc.).
        """
        try:
            self.scheduler.run()
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════
    # TUI (main thread)
    # ═══════════════════════════════════════════════════════════════

    def _run_tui_main(self) -> None:
        """
        Execute la TUI Textual dans le main thread.

        Textual requiert le main thread pour :
          - signal.signal(SIGTSTP, ...) dans LinuxDriver
          - signal.signal(SIGWINCH, ...) pour le resize terminal
          - Boucle asyncio principale

        Si la TUI crash, on la redemarre avec backoff exponentiel.
        Le scheduler continue dans son thread background.
        """
        configobj = self.config.get("configobj")
        mode = "deploy"
        if configobj:
            mode = configobj.get("env.mode", "deploy")

        while self._running:
            try:
                from ui.app import FsDeployApp

                app = FsDeployApp(
                    runtime=self.runtime,
                    store=self.store,
                    config=configobj,
                    mode=mode,
                )
                app.run()

                # app.run() retourne normalement = quit propre
                break

            except ImportError:
                # Textual pas installe — bascule en mode daemon
                break

            except Exception:
                # TUI crash — restart avec backoff
                auto_restart = self.config.get("tui_auto_restart", True)
                if not auto_restart or not self._running:
                    break
                time.sleep(self._tui_backoff)
                self._tui_backoff = min(
                    self._tui_backoff * 2,
                    self._tui_max_backoff,
                )
                continue

    # ═══════════════════════════════════════════════════════════════
    # MAIN
    # ═══════════════════════════════════════════════════════════════

    def run(self, mode: str = "tui") -> None:
        """
        Point d'entree principal.

        Modes :
          tui    : scheduler (thread) + TUI (main thread)
          daemon : scheduler seul (main thread, bloquant)
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

        # 6. Log demarrage
        self.store.log_event("daemon.started", source="daemon",
                             mode=mode, pid=str(os.getpid()))

        # 7. Scheduler dans un thread background (toujours)
        sched_thread = threading.Thread(
            target=self._run_scheduler_background,
            name="fsdeploy-scheduler",
            daemon=True,
        )
        sched_thread.start()

        # 8. TUI ou boucle d'attente dans le main thread
        try:
            tui_enabled = self.config.get("tui_enabled", True)
            if mode == "tui" and tui_enabled:
                # TUI dans le main thread (requis par Textual)
                self._run_tui_main()
            else:
                # Pas de TUI — attendre dans le main thread
                self._wait_main(sched_thread)
        except KeyboardInterrupt:
            pass
        finally:
            self._shutdown()

    def _wait_main(self, sched_thread: threading.Thread) -> None:
        """
        Boucle d'attente pour les modes sans TUI (daemon, bare, stream).
        Le main thread attend que le scheduler s'arrete ou qu'un signal arrive.
        """
        # Installer les signal handlers dans le main thread
        original_sigterm = signal.getsignal(signal.SIGTERM)
        original_sigint = signal.getsignal(signal.SIGINT)

        def _handle_stop(signum, frame):
            self._running = False
            self.scheduler.stop()

        signal.signal(signal.SIGTERM, _handle_stop)
        signal.signal(signal.SIGINT, _handle_stop)

        try:
            while self._running and sched_thread.is_alive():
                sched_thread.join(timeout=1.0)
        finally:
            signal.signal(signal.SIGTERM, original_sigterm)
            signal.signal(signal.SIGINT, original_sigint)

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


# ═══════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════

def _resolve_socket_path() -> str:
    """
    Determine le meilleur chemin pour le socket Unix.

    Priorite :
      1. /run/fsdeploy.sock   (si writable — root ou sudoers)
      2. $XDG_RUNTIME_DIR/fsdeploy.sock  (user session — systemd)
      3. /tmp/fsdeploy-<uid>.sock  (fallback universel)
    """
    # /run si accessible
    run_path = Path("/run/fsdeploy.sock")
    if run_path.parent.exists() and os.access(str(run_path.parent), os.W_OK):
        return str(run_path)

    # XDG_RUNTIME_DIR (ex: /run/user/1000)
    xdg = os.environ.get("XDG_RUNTIME_DIR", "")
    if xdg and Path(xdg).is_dir():
        return str(Path(xdg) / "fsdeploy.sock")

    # Fallback /tmp avec uid pour eviter les collisions
    return f"/tmp/fsdeploy-{os.getuid()}.sock"
