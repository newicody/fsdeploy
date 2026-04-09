"""
fsdeploy.scheduler.queue.intent_queue
======================================
File d'attente des intents.

Convertit les événements en intents via les EventHandler enregistrés.
Gère la file de priorité des intents en attente de traitement.
"""

import queue
import threading
from typing import Callable, Optional

from scheduler.model.intent import IntentID


class IntentQueue:
    """
    File d'attente thread-safe des intents avec priorité.
    Les intents avec une priorité plus basse (négative) sont traités en premier.
    """

    def __init__(self):
        self._queue: queue.PriorityQueue = queue.PriorityQueue()
        self._counter = 0
        self._priority_counter = 0  # tie‑breaker pour même priorité
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
            # Si l'intent n'a pas de priorité, utiliser celle de l'événement
            if not hasattr(intent, 'priority'):
                intent.priority = getattr(event, 'priority', 0)
            elif hasattr(event, 'priority'):
                # Si l'intent a déjà une priorité, on pourrait la conserver
                pass

        return intents

    # ── Queue operations ──────────────────────────────────────────────────────

    def push(self, intent) -> None:
        """Ajoute un intent à la queue."""
        if not intent.id or intent.id.get() == "0":
            intent.id = self._next_id()
        # Priorité par défaut = 0
        priority = getattr(intent, 'priority', 0)
        with self._lock:
            self._priority_counter += 1
            self._queue.put((priority, self._priority_counter, intent))

    def put(self, intent) -> None:
        """Alias de push pour compatibilité."""
        self.push(intent)

    def pop(self, timeout: float | None = None):
        """Récupère le prochain intent."""
        try:
            _, _, intent = self._queue.get(timeout=timeout)
            return intent
        except queue.Empty:
            return None

    def pop_many(self, n: int, timeout: float | None = None) -> list:
        """
        Récupère jusqu'à n intents de la queue.
        Si timeout n'est pas None, attend au plus timeout secondes pour le
        premier intent; les suivants sans attente.
        Retourne une liste (éventuellement vide).
        """
        intents = []
        try:
            # Premier intent avec timeout
            _, _, intent = self._queue.get(timeout=timeout)
            intents.append(intent)
            # Récupérer les suivants sans attente (block=False)
            for _ in range(n - 1):
                try:
                    _, _, intent = self._queue.get_nowait()
                    intents.append(intent)
                except queue.Empty:
                    break
        except queue.Empty:
            pass
        return intents

    def get(self, timeout: float | None = 0):
        """Alias non-bloquant par défaut."""
        return self.pop(timeout=timeout)

    def empty(self) -> bool:
        return self._queue.empty()

    def qsize(self) -> int:
        return self._queue.qsize()
