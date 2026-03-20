"""
fsdeploy.scheduler.queue.event_queue
=====================================
File d'attente des événements entrants.

Sources : CLI, bus (socket/dbus/udev/inotify), scheduler interne, cron, init system.
Thread-safe via queue.PriorityQueue.
"""

import queue
import time
from typing import Optional


class EventQueue:
    """
    File d'attente thread-safe des événements.
    Les événements urgents (priority négatif) sortent en premier.
    """

    def __init__(self, maxsize: int = 0):
        self._queue: queue.PriorityQueue = queue.PriorityQueue(maxsize=maxsize)
        self._counter = 0  # tie-breaker pour événements de même priorité

    def push(self, event) -> None:
        """Ajoute un événement."""
        priority = getattr(event, "priority", 0)
        self._counter += 1
        self._queue.put((priority, self._counter, event))

    def put(self, event) -> None:
        """Alias de push pour compatibilité avec queue.Queue."""
        self.push(event)

    def pop(self, timeout: float | None = None):
        """Récupère le prochain événement (bloquant par défaut)."""
        try:
            _, _, event = self._queue.get(timeout=timeout)
            return event
        except queue.Empty:
            return None

    def get(self, timeout: float | None = 0):
        """Alias non-bloquant par défaut pour compatibilité."""
        return self.pop(timeout=timeout)

    def empty(self) -> bool:
        return self._queue.empty()

    def qsize(self) -> int:
        return self._queue.qsize()

    def clear(self) -> None:
        """Vide la queue."""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
