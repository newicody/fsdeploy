"""
fsdeploy.scheduler.intentlog.log
=================================
Journal des intents exécutés.

Sert à :
  - Audit : traçabilité complète de qui a fait quoi
  - Replay : rejouer une séquence d'intents
  - Debug : diagnostic des échecs
"""

import json
import time
from pathlib import Path
from typing import Any, Optional


class IntentLogEntry:
    """Entrée dans le journal."""

    __slots__ = ("intent_id", "intent_class", "status", "timestamp",
                 "duration", "error", "params", "tasks")

    def __init__(self, intent_id: str, intent_class: str,
                 status: str = "pending", params: dict | None = None):
        self.intent_id = intent_id
        self.intent_class = intent_class
        self.status = status
        self.timestamp = time.time()
        self.duration = 0.0
        self.error: str | None = None
        self.params = params or {}
        self.tasks: list[dict] = []

    def to_dict(self) -> dict:
        return {
            "id": self.intent_id,
            "class": self.intent_class,
            "status": self.status,
            "timestamp": self.timestamp,
            "duration": self.duration,
            "error": self.error,
            "params": self.params,
            "tasks": self.tasks,
        }


class IntentLog:
    """
    Journal persistant des intents.
    Stocké en JSONL (un JSON par ligne) dans var/log/fsdeploy/.
    """

    def __init__(self, log_dir: str | Path | None = None):
        self._entries: list[IntentLogEntry] = []
        self._log_path: Path | None = None

        if log_dir:
            self._log_path = Path(log_dir) / "intent.log"
            self._log_path.parent.mkdir(parents=True, exist_ok=True)

    def record_start(self, intent) -> IntentLogEntry:
        """Enregistre le début d'un intent."""
        entry = IntentLogEntry(
            intent_id=intent.get_id(),
            intent_class=intent.__class__.__name__,
            status="running",
            params=getattr(intent, "params", {}),
        )
        self._entries.append(entry)
        return entry

    def record_success(self, entry: IntentLogEntry, tasks_completed: int = 0) -> None:
        entry.status = "completed"
        entry.duration = time.time() - entry.timestamp
        self._persist(entry)

    def record_failure(self, entry: IntentLogEntry, error: Exception | str) -> None:
        entry.status = "failed"
        entry.error = str(error)
        entry.duration = time.time() - entry.timestamp
        self._persist(entry)

    def _persist(self, entry: IntentLogEntry) -> None:
        """Écrit une ligne JSONL."""
        if self._log_path:
            try:
                with open(self._log_path, "a") as f:
                    f.write(json.dumps(entry.to_dict()) + "\n")
            except OSError:
                pass

    def get_history(self, limit: int = 100) -> list[dict]:
        """Retourne les N dernières entrées."""
        return [e.to_dict() for e in self._entries[-limit:]]

    def get_failures(self, limit: int = 50) -> list[dict]:
        """Retourne les échecs récents."""
        return [
            e.to_dict() for e in self._entries[-limit:]
            if e.status == "failed"
        ]

    @property
    def total_count(self) -> int:
        return len(self._entries)

    @property
    def failure_count(self) -> int:
        return sum(1 for e in self._entries if e.status == "failed")
