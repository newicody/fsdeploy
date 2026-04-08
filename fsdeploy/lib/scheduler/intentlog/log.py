"""
fsdeploy.scheduler.intentlog.log
=================================
Journal des intents exécutés.

Sert à :
  - Audit : traçabilité complète de qui a fait quoi
  - Replay : rejouer une séquence d'intents
  - Debug : diagnostic des échecs

Ce journal utilise un format JSONL persistant sur disque (fichier texte).
Il peut également être connecté au store compressé (HuffmanStore) via
l'attribut `store`. Dans ce cas, chaque entrée est également ajoutée
sous forme compressée au HuffmanStore, permettant une analyse rapide
et une visualisation via la TUI tout en conservant une trace textuelle
pour une consultation manuelle.
"""

import json
import time
import traceback
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional
from .codec import HuffmanStore


class IntentLogEntry:
    """Entrée dans le journal."""

    __slots__ = ("intent_id", "intent_class", "status", "timestamp",
                 "duration", "error", "params", "tasks", "traceback", "context", "severity")

    def __init__(self, intent_id: str, intent_class: str,
                 status: str = "pending", params: dict | None = None,
                 traceback: str | None = None, context: dict | None = None,
                 severity: str = "info"):
        self.intent_id = intent_id
        self.intent_class = intent_class
        self.status = status
        self.timestamp = time.time()
        self.duration = 0.0
        self.error: str | None = None
        self.params = params or {}
        self.tasks: list[dict] = []
        self.traceback = traceback
        self.context = context
        self.severity = severity

    def to_dict(self) -> dict:
        d = {
            "id": self.intent_id,
            "class": self.intent_class,
            "status": self.status,
            "timestamp": self.timestamp,
            "duration": self.duration,
            "error": self.error,
            "params": self.params,
            "tasks": self.tasks,
            "severity": self.severity,
        }
        if self.traceback is not None:
            d["traceback"] = self.traceback
        if self.context is not None:
            d["context"] = self.context
        return d


class IntentLog:
    """
    Journal persistant des intents.
    Stocké en JSONL (un JSON par ligne) dans var/log/fsdeploy/.
    """

    def __init__(self, log_dir: str | Path | None = None):
        self._entries: list[IntentLogEntry] = []
        self._log_path: Path | None = None
        self.huffman_store = HuffmanStore()
        self.store = self.huffman_store.intents

        if log_dir:
            self._log_path = Path(log_dir) / "intent.log"
            self._log_path.parent.mkdir(parents=True, exist_ok=True)

    def record_start(self, intent, context: dict | None = None, severity: str = "info") -> IntentLogEntry:
        """Enregistre le début d'un intent."""
        entry = IntentLogEntry(
            intent_id=intent.get_id(),
            intent_class=intent.__class__.__name__,
            status="running",
            params=getattr(intent, "params", {}),
            context=context,
            severity=severity,
        )
        self._entries.append(entry)
        return entry

    def record_success(self, entry: IntentLogEntry, tasks_completed: int = 0) -> None:
        entry.status = "completed"
        entry.duration = time.time() - entry.timestamp
        self._persist(entry)

    def record_failure(self, entry: IntentLogEntry, error: Exception | str, context: dict | None = None) -> None:
        entry.status = "failed"
        entry.error = str(error)
        if isinstance(error, Exception):
            entry.traceback = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
        else:
            entry.traceback = None
        if context is not None:
            entry.context = context
        entry.severity = "error"
        entry.duration = time.time() - entry.timestamp
        self._persist(entry)

    def _persist(self, entry: IntentLogEntry) -> None:
        """Écrit une ligne JSONL."""
        if self._log_path:
            try:
                with open(self._log_path, "a", buffering=1) as f:
                    f.write(json.dumps(entry.to_dict()) + "\n")
            except OSError:
                pass
        # Si un store compressé est attaché, y ajouter également un enregistrement
        if self.store is not None:
            try:
                from .codec import Record
                record = Record(
                    timestamp=entry.timestamp,
                    category="intent",
                    action=entry.status,
                    severity=entry.severity,
                    tokens=[entry.intent_id, entry.intent_class],
                    meta=entry.to_dict(),
                )
                self.store.append(record)
            except Exception:
                # Ignorer les erreurs pour ne pas perturber le flux principal
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

    def get_by_severity(self, severity: str, limit: int = 100) -> list[dict]:
        """Retourne les entrées avec un niveau de sévérité donné."""
        filtered = [e.to_dict() for e in self._entries if e.severity == severity]
        if limit > 0:
            return filtered[-limit:]
        return filtered

    def get_by_severity_and_time(self, severity: str, start_time: float, end_time: float,
                                 limit: int = 100) -> list[dict]:
        """Retourne les entrées avec un niveau de sévérité donné dans une plage de temps."""
        filtered = []
        # Parcours inversé car les entrées sont ajoutées dans l'ordre chronologique croissant
        for entry in reversed(self._entries):
            if entry.severity != severity:
                continue
            if entry.timestamp < start_time:
                break
            if entry.timestamp <= end_time:
                filtered.append(entry.to_dict())
                if len(filtered) >= limit:
                    break
        filtered.reverse()
        return filtered

    def export_json(self, path: str | Path, severity: str | None = None,
                    start_time: float | None = None, end_time: float | None = None,
                    limit: int = 10_000) -> None:
        """
        Exporte les logs d'intentions dans un fichier JSON (non compressé).
        Les paramètres permettent de filtrer par sévérité et plage de temps.
        """
        import json
        from pathlib import Path
        output = []
        for entry in self._entries:
            if severity is not None and entry.severity != severity:
                continue
            if start_time is not None and entry.timestamp < start_time:
                continue
            if end_time is not None and entry.timestamp > end_time:
                continue
            output.append(entry.to_dict())
            if len(output) >= limit:
                break
        path_obj = Path(path)
        path_obj.parent.mkdir(parents=True, exist_ok=True)
        with open(path_obj, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False, default=str)

    def severity_counts(self) -> dict[str, int]:
        """Retourne un dictionnaire avec le nombre d'entrées par sévérité."""
        counts = defaultdict(int)
        for entry in self._entries:
            counts[entry.severity] += 1
        return dict(counts)

    def stats(self) -> dict[str, Any]:
        """Retourne un dictionnaire combinant les statistiques du journal et du store compressé."""
        hstore_stats = self.huffman_store.stats()
        return {
            "intent_log": {
                "total_entries": self.total_count,
                "failed_entries": self.failure_count,
                "severity_counts": self.severity_counts(),
            },
            "huffman_store": hstore_stats,
        }

    @property
    def total_count(self) -> int:
        return len(self._entries)

    @property
    def failure_count(self) -> int:
        return sum(1 for e in self._entries if e.status == "failed")


# Instance globale utilisée par le scheduler et l'UI
intent_log = IntentLog()


def get_global_huffman_store():
    """
    Retourne le HuffmanStore global (celui attaché à intent_log).
    """
    return intent_log.huffman_store
