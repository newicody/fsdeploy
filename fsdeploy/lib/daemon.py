# -*- coding: utf-8 -*-
"""
fsdeploy.daemon
================
Processus racine - orchestre le scheduler, les bus et la TUI.

Hierarchie :
  daemon (racine)
  +-- scheduler (thread background daemon)
  |   +-- ThreadPoolExecutor (tasks threaded)
  +-- TUI Textual (main thread - obligatoire pour Textual 8.x)

Modes :
  tui     -> scheduler background + TUI main thread (defaut)
  daemon  -> scheduler main thread, pas de TUI
  bare    -> scheduler main thread, pas de TUI, pas de bus
  stream  -> scheduler background + TUI en mode stream
"""

import os
import sys
import signal
import threading
import time
from pathlib import Path
from typing import Any, Optional

# Force UTF-8 pour eviter les erreurs textual serve
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from log import get_logger

log = get_logger("daemon")


def _is_main_thread() -> bool:
    return threading.current_thread() is threading.main_thread()


class FsDeployDaemon:
    """Processus racine fsdeploy."""

    def __init__(self, config: dict | None = None):
        self._config = config or {}
        self._scheduler = None
        self._executor = None
        self._runtime = None
        self._store = None
        self._bus_sources = []
        self._scheduler_thread: Optional[threading.Thread] = None
        self._running = False

    # ===================================================================
    # LIFECYCLE
    # ===================================================================

    def run(self, mode: str = "tui") -> None:
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
            if mode != "bare":
                self._start_bus()
            self._install_signals()
            log.info("scheduler_main_thread", mode=mode)
            self._scheduler.run()
        else:
            self._start_bus()
            self._start_scheduler_background()
            self._run_tui(mode=mode)

    def stop(self) -> None:
        log.info("daemon_stop")
        self._running = False
        if self._scheduler:
            self._scheduler.stop()
        for source in self._bus_sources:
            try:
                source.stop()
            except Exception:
                pass
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            self._scheduler_thread.join(timeout=5)
        if self._executor:
            try:
                self._executor.shutdown()
            except Exception:
                pass
        log.info("daemon_stopped")

    # ===================================================================
    # INIT
    # ===================================================================

    def _init_store(self) -> None:
        try:
            from scheduler.intentlog.codec import HuffmanStore
            self._store = HuffmanStore()
            log.info("store_ready")
        except ImportError:
            log.warning("store_unavailable")
            self._store = None

    def _init_runtime(self) -> None:
        from scheduler.core.runtime import Runtime
        self._runtime = Runtime()
        log.info("runtime_ready")

    def _init_executor(self) -> None:
        from scheduler.core.executor import Executor
        max_workers = self._config.get("scheduler", {}).get("max_workers", 4)
        self._executor = Executor(
            runtime=self._runtime,
            max_workers=max_workers,
        )
        log.info("executor_ready", max_workers=max_workers)

    def _init_scheduler(self) -> None:
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
        from scheduler.core.registry import INTENT_REGISTRY

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

        intent_queue = self._runtime.intent_queue
        for event_name, intent_class in INTENT_REGISTRY.items():
            def _make_handler(cls):
                def handler(event):
                    return [cls(params=event.params, context=event.params)]
                return handler
            intent_queue.register_handler(event_name, _make_handler(intent_class))

    # ===================================================================
    # BUS
    # ===================================================================

    def _start_bus(self) -> None:
        from bus import TimerSource, InotifySource, UdevSource, SocketSource

        eq = self._runtime.event_queue
        sched_cfg = self._config.get("scheduler", {})

        timer = TimerSource(eq)
        timer.add_job("coherence_check", 3600)
        timer.add_job("scrub_check", 604800)
        timer.start()
        self._bus_sources.append(timer)
        log.info("bus_timer_started")

        if sched_cfg.get("bus_inotify", True):
            try:
                inotify = InotifySource(eq, watch_paths=["/boot"])
                inotify.start()
                self._bus_sources.append(inotify)
                log.info("bus_inotify_started")
            except Exception as e:
                log.warning("bus_inotify_failed", error=str(e))

        if sched_cfg.get("bus_udev", True):
            try:
                udev = UdevSource(eq)
                udev.start()
                self._bus_sources.append(udev)
                log.info("bus_udev_started")
            except Exception as e:
                log.warning("bus_udev_failed", error=str(e))

        if sched_cfg.get("bus_socket", True):
            socket_path = sched_cfg.get("socket_path", "/run/fsdeploy.sock")
            try:
                sock = SocketSource(eq, socket_path=socket_path)
                sock.start()
                self._bus_sources.append(sock)
                log.info("bus_socket_started", path=sock.effective_path)
            except Exception as e:
                log.warning("bus_socket_failed", error=str(e))

    # ===================================================================
    # SCHEDULER THREAD
    # ===================================================================

    def _start_scheduler_background(self) -> None:
        self._scheduler_thread = threading.Thread(
            target=self._scheduler.run,
            name="fsdeploy-scheduler",
            daemon=True,
        )
        self._scheduler_thread.start()
        log.info("scheduler_background_started")

    # ===================================================================
    # TUI
    # ===================================================================

    def _run_tui(self, mode: str = "tui") -> None:
        try:
            from ui.app import FsDeployApp
        except ImportError as e:
            log.error("tui_import_failed", error=str(e))
            log.info("fallback_scheduler_main")
            self._install_signals()
            if self._scheduler_thread:
                self._scheduler_thread.join()
            return

        tui_mode = "stream" if mode == "stream" else "deploy"
        app_config = None
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
                log.info("tui_exited_normally")
                break
            except KeyboardInterrupt:
                log.info("tui_keyboard_interrupt")
                break
            except Exception as e:
                log.error("tui_crashed", error=str(e), backoff=backoff)
                if not auto_restart:
                    break
                log.info("tui_restart", delay=backoff)
                time.sleep(backoff)
                backoff = min(backoff * 2, max_backoff)

        self.stop()

    # ===================================================================
    # SIGNAUX
    # ===================================================================

    def _install_signals(self) -> None:
        if not _is_main_thread():
            return

        def _handler(signum, frame):
            log.info("signal_received", signal=signum)
            self.stop()

        signal.signal(signal.SIGTERM, _handler)
        signal.signal(signal.SIGINT, _handler)

    # ===================================================================
    # INTROSPECTION
    # ===================================================================

    def get_state_snapshot(self) -> dict:
        result = {"running": self._running, "bus_sources": len(self._bus_sources)}
        if self._runtime:
            try:
                result["event_count"] = self._runtime.event_queue.qsize()
                result["intent_count"] = self._runtime.intent_queue.qsize()
            except Exception:
                pass
        if self._scheduler:
            result["scheduler_running"] = self._scheduler._running
        if self._executor:
            result["executor_pending"] = getattr(self._executor, 'pending_count', 0)
        return result
