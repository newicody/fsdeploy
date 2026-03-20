"""
fsdeploy.scheduler.runtime.monitor
====================================
Monitoring et observabilité du scheduler.

Fournit des métriques et du logging pour la TUI et le debug.
"""

import time
import threading
from typing import Any, Callable, Optional


class RuntimeMonitor:
    """
    Collecte les métriques du scheduler et notifie les observers.
    """

    def __init__(self):
        self._observers: list[Callable] = []
        self._log_entries: list[dict] = []
        self._lock = threading.Lock()
        self._counters = {
            "events_processed": 0,
            "intents_processed": 0,
            "tasks_executed": 0,
            "tasks_failed": 0,
            "cycles": 0,
        }

    def log(self, message: str, level: str = "info") -> None:
        entry = {
            "time": time.time(),
            "level": level,
            "message": message,
        }
        with self._lock:
            self._log_entries.append(entry)
            if len(self._log_entries) > 10000:
                self._log_entries = self._log_entries[-5000:]
        self._notify("log", entry)

    def log_error(self, task, error: Exception) -> None:
        self.log(f"Task {task} failed: {error}", level="error")
        with self._lock:
            self._counters["tasks_failed"] += 1

    def increment(self, counter: str, value: int = 1) -> None:
        with self._lock:
            self._counters[counter] = self._counters.get(counter, 0) + value

    def add_observer(self, callback: Callable) -> None:
        self._observers.append(callback)

    def remove_observer(self, callback: Callable) -> None:
        try:
            self._observers.remove(callback)
        except ValueError:
            pass

    def _notify(self, event_type: str, data: Any) -> None:
        for obs in self._observers:
            try:
                obs(event_type, data)
            except Exception:
                pass

    @property
    def counters(self) -> dict[str, int]:
        with self._lock:
            return dict(self._counters)

    def recent_logs(self, limit: int = 50) -> list[dict]:
        with self._lock:
            return list(self._log_entries[-limit:])
