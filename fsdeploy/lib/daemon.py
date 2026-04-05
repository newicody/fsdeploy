"""
fsdeploy.daemon
================
Processus racine — orchestre le scheduler, les bus et la TUI.

Hierarchie :
  daemon (racine)
  ├── scheduler (thread background daemon)
  │   └── ThreadPoolExecutor (tasks threaded)
  └── TUI Textual (main thread — obligatoire pour Textual 8.x)

Architecture de threads :
  - TUI Textual DOIT tourner dans le main thread (contrainte Textual 8.x)
  - Le Scheduler tourne dans un thread background (daemon=True)
  - Les signal handlers ne sont installes que dans le main thread
  - Si la TUI crash, le scheduler continue (processus resilient)

Modes :
  tui     → scheduler background + TUI main thread (defaut)
  daemon  → scheduler main thread, pas de TUI
  bare    → scheduler main thread, pas de TUI, pas de bus
  stream  → scheduler background + TUI en mode stream
"""

import os
import sys
import signal
import threading
import time
from pathlib import Path
from typing import Any, Optional

from log import get_logger

log = get_logger("daemon")


def _is_main_thread() -> bool:
    return threading.current_thread() is threading.main_thread()


class FsDeployDaemon:
    """
    Processus racine fsdeploy.

    Orchestre :
      1. Config (dict ou FsDeployConfig)
      2. HuffmanStore (BDD compacte in-memory)
      3. Runtime (state + queues)
      4. Scheduler (boucle event→intent→task)
      5. Executor (ThreadPoolExecutor)
      6. Bus sources (Timer, Inotify, Udev, Socket)
      7. Intent registry (wiring handlers)
      8. TUI Textual (main thread, optionnel)
    """

    def __init__(self, config: dict | None = None):
        self._config = config or {}
        self._scheduler = None
        self._executor = None
        self._runtime = None
        self._store = None
        self._bus_sources = []
        self._scheduler_thread: Optional[threading.Thread] = None
        self._running = False

    # ═══════════════════════════════════════════════════════════════
    # LIFECYCLE
    # ═══════════════════════════════════════════════════════════════

    def run(self, mode: str = "tui") -> None:
        """
        Point d'entree principal.

        Args:
            mode: tui | daemon | bare | stream
        """
        log.info("daemon_start", mode=mode)

        try:
            self._init_store()
            self._init_runtime()
            self._init_executor()
            self._init_scheduler()
            self._register_all_intents()
        except Exception as e:
            log.error("init_failed", error=str(e))
            raise

        if mode in ("daemon", "bare"):
            # Pas de TUI — scheduler dans le main thread
            if mode != "bare":
                self._start_bus()
            self._install_signals()
            log.info("scheduler_main_thread", mode=mode)
            self._scheduler.run()  # bloquant
        else:
            # TUI mode — scheduler en background, TUI en main thread
            self._start_bus()
            self._start_scheduler_background()
            self._run_tui(mode=mode)

    def stop(self) -> None:
        """Arret propre de tout."""
        log.info("daemon_stop")
        self._running = False

        # Arreter le scheduler
        if self._scheduler:
            self._scheduler.stop()

        # Arreter les bus
        for source in self._bus_sources:
            try:
                source.stop()
            except Exception:
                pass

        # Attendre le thread scheduler
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            self._scheduler_thread.join(timeout=5)

        # Arreter l'executor
        if self._executor:
            try:
                self._executor.shutdown()
            except Exception:
                pass

        log.info("daemon_stopped")

    # ═══════════════════════════════════════════════════════════════
    # INIT
    # ═══════════════════════════════════════════════════════════════

    def _init_store(self) -> None:
        """Initialise le HuffmanStore."""
        try:
            from scheduler.intentlog.codec import HuffmanStore
            self._store = HuffmanStore()
            log.info("store_ready")
        except ImportError:
            log.warning("store_unavailable", reason="intentlog.codec not found")
            self._store = None

    def _init_runtime(self) -> None:
        """Initialise le Runtime (state + queues)."""
        from scheduler.core.runtime import Runtime
        self._runtime = Runtime()
        log.info("runtime_ready")

    def _init_executor(self) -> None:
        """Initialise l'Executor avec ThreadPoolExecutor."""
        from scheduler.core.executor import Executor

        max_workers = self._config.get("scheduler", {}).get("max_workers", 4)
        self._executor = Executor(
            runtime=self._runtime,
            max_workers=max_workers,
            store=self._store,
        )
        log.info("executor_ready", max_workers=max_workers)

    def _init_scheduler(self) -> None:
        """Initialise le Scheduler."""
        from scheduler.core.resolver import Resolver
        from scheduler.core.scheduler import Scheduler

        resolver = Resolver(self._runtime)
        tick = self._config.get("scheduler", {}).get("tick_interval", 0.1)

        self._scheduler = Scheduler(
            resolver=resolver,
            executor=self._executor,
            runtime=self._runtime,
        )
        self._scheduler._tick_interval = tick
        log.info("scheduler_ready", tick_interval=tick)

    def _register_all_intents(self) -> None:
        """
        Enregistre tous les intent handlers.

        Les modules intents/ utilisent @register_intent qui peuple
        INTENT_REGISTRY. On doit wirer ce registry dans
        IntentQueue._handlers pour que le scheduler les trouve.
        """
        from scheduler.core.registry import INTENT_REGISTRY
        from scheduler.queue.intent_queue import IntentQueue

        # Importer tous les modules intents pour forcer l'enregistrement
        intent_modules = [
            "intents.detection_intent",
            "intents.boot_intent",
            "intents.kernel_intent",
            "intents.system_intent",
            "intents.test_intent",
        ]

        for mod_name in intent_modules:
            try:
                __import__(mod_name)
            except ImportError as e:
                log.warning("intent_import_failed", module=mod_name, error=str(e))

        # Wirer INTENT_REGISTRY → IntentQueue._handlers
        intent_queue = self._runtime.intent_queue
        if hasattr(intent_queue, '_handlers'):
            for event_name, intent_class in INTENT_REGISTRY.items():
                intent_queue._handlers[event_name] = intent_class
            log.info("intents_wired",
                     count=len(INTENT_REGISTRY),
                     events=list(INTENT_REGISTRY.keys()))
        else:
            log.warning("intent_queue_no_handlers",
                        msg="IntentQueue has no _handlers attribute")

    # ═══════════════════════════════════════════════════════════════
    # BUS
    # ═══════════════════════════════════════════════════════════════

    def _start_bus(self) -> None:
        """Demarre les sources d'evenements du bus."""
        from bus import TimerSource, InotifySource, UdevSource, SocketSource

        eq = self._runtime.event_queue
        sched_cfg = self._config.get("scheduler", {})

        # Timer — toujours actif
        timer = TimerSource(eq)
        timer.add_job("coherence_check", 3600)
        timer.add_job("scrub_check", 604800)
        timer.start()
        self._bus_sources.append(timer)
        log.info("bus_timer_started")

        # Inotify
        if sched_cfg.get("bus_inotify", True):
            try:
                inotify = InotifySource(eq, watch_paths=["/boot"])
                inotify.start()
                self._bus_sources.append(inotify)
                log.info("bus_inotify_started")
            except Exception as e:
                log.warning("bus_inotify_failed", error=str(e))

        # Udev
        if sched_cfg.get("bus_udev", True):
            try:
                udev = UdevSource(eq)
                udev.start()
                self._bus_sources.append(udev)
                log.info("bus_udev_started")
            except Exception as e:
                log.warning("bus_udev_failed", error=str(e))

        # Socket
        if sched_cfg.get("bus_socket", True):
            socket_path = sched_cfg.get("socket_path", "/run/fsdeploy.sock")
            try:
                sock = SocketSource(eq, socket_path=socket_path)
                sock.start()
                self._bus_sources.append(sock)
                log.info("bus_socket_started", path=sock.effective_path)
            except Exception as e:
                log.warning("bus_socket_failed", error=str(e))

    # ═══════════════════════════════════════════════════════════════
    # SCHEDULER THREAD
    # ═══════════════════════════════════════════════════════════════

    def _start_scheduler_background(self) -> None:
        """Demarre le scheduler dans un thread background daemon."""
        self._scheduler_thread = threading.Thread(
            target=self._scheduler.run,
            name="fsdeploy-scheduler",
            daemon=True,
        )
        self._scheduler_thread.start()
        log.info("scheduler_background_started")

    # ═══════════════════════════════════════════════════════════════
    # TUI
    # ═══════════════════════════════════════════════════════════════

    def _run_tui(self, mode: str = "tui") -> None:
        """
        Lance la TUI Textual dans le main thread.

        Textual 8.x EXIGE le main thread pour les signaux
        (SIGWINCH, SIGTSTP, etc.) et pour asyncio.
        """
        try:
            from ui.app import FsDeployApp
        except ImportError as e:
            log.error("tui_import_failed", error=str(e))
            # Fallback : scheduler en main thread
            log.info("fallback_scheduler_main")
            self._install_signals()
            self._scheduler_thread.join()
            return

        tui_mode = "stream" if mode == "stream" else "deploy"
        app_config = None

        # Charger le FsDeployConfig si disponible
        try:
            from config import FsDeployConfig
            app_config = FsDeployConfig.default(create=False)
        except Exception:
            pass

        log.info("tui_starting", mode=tui_mode)

        tui_cfg = self._config.get("tui", {})
        auto_restart = tui_cfg.get("auto_restart", True)
        max_backoff = tui_cfg.get("max_backoff", 60)
        backoff = 1

        while True:
            try:
                app = FsDeployApp(
                    runtime=self._runtime,
                    store=self._store,
                    config=app_config,
                    mode=tui_mode,
                )
                app.run()
                # Sortie normale (q pressed)
                log.info("tui_exited_normally")
                break

            except KeyboardInterrupt:
                log.info("tui_keyboard_interrupt")
                break

            except Exception as e:
                log.error("tui_crashed", error=str(e), backoff=backoff)

                if not auto_restart:
                    log.info("tui_no_restart")
                    break

                log.info("tui_restart", delay=backoff)
                time.sleep(backoff)
                backoff = min(backoff * 2, max_backoff)

        # Quand la TUI quitte, arreter proprement
        self.stop()

    # ═══════════════════════════════════════════════════════════════
    # SIGNAUX
    # ═══════════════════════════════════════════════════════════════

    def _install_signals(self) -> None:
        """Installe les signal handlers dans le main thread."""
        if not _is_main_thread():
            return

        def _handler(signum, frame):
            log.info("signal_received", signal=signum)
            self.stop()

        signal.signal(signal.SIGTERM, _handler)
        signal.signal(signal.SIGINT, _handler)

    # ═══════════════════════════════════════════════════════════════
    # INTROSPECTION
    # ═══════════════════════════════════════════════════════════════

    def get_state_snapshot(self) -> dict:
        """Snapshot pour GraphView et monitoring externe."""
        result = {
            "running": self._running,
            "bus_sources": len(self._bus_sources),
        }
        if self._runtime:
            try:
                eq = self._runtime.event_queue
                iq = self._runtime.intent_queue
                result["event_count"] = eq.qsize() if hasattr(eq, 'qsize') else 0
                result["intent_count"] = iq.qsize() if hasattr(iq, 'qsize') else 0
            except Exception:
                pass
        if self._scheduler:
            result["scheduler_running"] = self._scheduler._running
        if self._executor:
            result["executor_pending"] = getattr(self._executor, 'pending_count', 0)
        return result
