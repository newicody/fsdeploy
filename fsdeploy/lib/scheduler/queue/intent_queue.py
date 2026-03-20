"""
fsdeploy.scheduler.queue.intent_queue
======================================
File d'attente des intents.

Convertit les événements en intents via les EventHandler enregistrés.
Gère la file FIFO des intents en attente de traitement.
"""

import queue
import threading
from typing import Callable, Optional

from scheduler.model.intent import IntentID


class IntentQueue:
    """
    File d'attente FIFO thread-safe des intents.
    """

    def __init__(self):
        self._queue: queue.Queue = queue.Queue()
        self._counter = 0
        self._lock = threading.Lock()

        # Handlers : event.name → callable(event) → list[Intent]
        self._handlers: dict[str, list[Callable]] = {}

    # ── ID generation ─────────────────────────────────────────────────────────

    def _next_id(self) -> IntentID:
        with self._lock:
            self._counter += 1
            return IntentID(str(self._counter))

    # ── Event → Intent conversion ─────────────────────────────────────────────

    def register_handler(self, event_name: str, handler: Callable) -> None:
        """
        Enregistre un handler qui convertit un event en intents.
        handler(event) → list[Intent]
        """
        self._handlers.setdefault(event_name, []).append(handler)

    def create_from_event(self, event) -> list:
        """
        Convertit un événement en intents via les handlers enregistrés.
        Retourne la liste d'intents créés.
        """
        intents = []
        handlers = self._handlers.get(event.name, [])

        # Handlers globaux (wildcard)
        handlers += self._handlers.get("*", [])

        for handler in handlers:
            try:
                result = handler(event)
                if result:
                    if isinstance(result, list):
                        intents.extend(result)
                    else:
                        intents.append(result)
            except Exception:
                pass  # logged par le caller

        # Assigner des IDs aux intents qui n'en ont pas
        for intent in intents:
            if not intent.id or intent.id.get() == "0":
                intent.id = self._next_id()

        return intents

    # ── Queue operations ──────────────────────────────────────────────────────

    def push(self, intent) -> None:
        """Ajoute un intent à la queue."""
        if not intent.id or intent.id.get() == "0":
            intent.id = self._next_id()
        self._queue.put(intent)

    def put(self, intent) -> None:
        """Alias de push pour compatibilité."""
        self.push(intent)

    def pop(self, timeout: float | None = None):
        """Récupère le prochain intent."""
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def get(self, timeout: float | None = 0):
        """Alias non-bloquant par défaut."""
        return self.pop(timeout=timeout)

    def empty(self) -> bool:
        return self._queue.empty()

    def qsize(self) -> int:
        return self._queue.qsize()
