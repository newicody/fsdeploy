"""
fsdeploy.scheduler.core.runtime
================================
Runtime : conteneur central agrégant state + queues.

Le Runtime est le seul objet partagé entre Scheduler, Executor, et les Tasks.
"""

from scheduler.model.runtime import RuntimeState
from scheduler.queue.event_queue import EventQueue
from scheduler.queue.intent_queue import IntentQueue


class Runtime:
    """
    Contexte d'exécution partagé du scheduler.
    """

    def __init__(self):
        self.state = RuntimeState()
        self.event_queue = EventQueue()
        self.intent_queue = IntentQueue()

        # Configuration runtime
        self.dry_run: bool = False
        self.verbose: bool = False
        self.bypass: bool = False

    # ── Délégation vers RuntimeState ──────────────────────────────────────────

    def can_run(self, resources) -> bool:
        return self.state.can_run(resources)

    def add_running(self, task) -> None:
        self.state.add_running(task)

    def add_waiting(self, task) -> None:
        self.state.add_waiting(task)

    def remove_waiting(self, task) -> None:
        self.state.remove_waiting(task)

    def fail(self, obj, error) -> None:
        """Gère l'échec d'un intent ou d'une task."""
        if hasattr(obj, "mark_failed"):
            obj.mark_failed(error)
        self.state.fail(obj, error)

    # ── Introspection ─────────────────────────────────────────────────────────

    @property
    def waiting_queue(self) -> list:
        """Compatibilité : retourne la liste des tasks en attente."""
        return self.state.get_waiting()

    def summary(self) -> str:
        return self.state.summary()
