"""
Pont (bridge) entre l'UI et le scheduler.

Permet aux écrans d'émettre des intents et de consulter l'état du scheduler.
"""
import threading
import time
import uuid
import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, List
from concurrent.futures import Future


@dataclass
class Ticket:
    """Référence à un événement ou un intent soumis au scheduler."""
    id: str
    event_name: str = ""
    params: dict = field(default_factory=dict)
    submitted_at: float = 0
    status: str = "pending"     # pending | completed | failed
    result: Any = None
    error: Optional[str] = None
    callbacks: list[Callable] = field(default_factory=list)


class SchedulerBridge:
    """
    Pont central entre l'interface utilisateur (ou tout autre client) et le scheduler.

    Cette classe permet d'émettre des événements et des intents vers le scheduler,
    de suivre leur exécution via des tickets, et d'interroger l'état du scheduler.

    Elle est implémentée comme un singleton ; utiliser `SchedulerBridge.default()`
    pour obtenir l'instance globale.

    Chaque événement ou intent soumis génère un ticket (objet `Ticket`) qui permet
    de connaître son statut (pending/completed/failed) et d'obtenir le résultat ou
    l'erreur associée.

    Le bridge assure la conversion des événements de priorité, l'injection d'un
    identifiant de ticket dans les paramètres, et la synchronisation périodique
    via `poll()` qui met à jour les tickets à partir de l'état du runtime.

    Attributes:
        _tickets: Dictionnaire des tickets en cours, indexés par leur ID.
        _history: File des derniers tickets terminés (max 500).
        _lock: Verrou pour les accès concurrents.
    """
    _instance = None

    @classmethod
    def default(cls) -> "SchedulerBridge":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        # Référence au scheduler (chargé à la demande)
        self._scheduler = None
        # Référence au bus d'événements global
        try:
            from fsdeploy.lib.bus.event_bus import MessageBus
            self._event_bus = MessageBus.global_instance()
        except ImportError:
            self._event_bus = None
        self._tickets: dict[str, Ticket] = {}
        self._history: deque[Ticket] = deque(maxlen=500)
        self._lock = threading.Lock()

    def _get_scheduler(self):
        if self._scheduler is None:
            try:
                from fsdeploy.lib.scheduler.core.scheduler import Scheduler
                self._scheduler = Scheduler.global_instance()
            except ImportError:
                self._scheduler = None
        return self._scheduler

    def _get_runtime_state(self):
        """Retourne le RuntimeState du scheduler."""
        scheduler = self._get_scheduler()
        if scheduler is not None and hasattr(scheduler, 'runtime'):
            return scheduler.runtime
        # Fallback: essayer d'importer le runtime global
        try:
            from fsdeploy.lib.scheduler.model.runtime import get_global_runtime
            return get_global_runtime()
        except ImportError:
            return None

    def _log_ticket(self, action: str, ticket: Ticket, **extra):
        """Émet un événement de log pour un ticket."""
        if self._event_bus is None:
            return
        self._event_bus.emit(
            "bridge.ticket." + action,
            ticket_id=ticket.id,
            event_name=ticket.event_name,
            status=ticket.status,
            **extra
        )

    # ═══════════════════════════════════════════════════════════════
    # Émission d'événements
    # ═══════════════════════════════════════════════════════════════

    def submit_event(self, event_name: str, priority: int | None = None, **params) -> str:
        """Émet un événement prioritaire vers le scheduler.
        Retourne un identifiant de ticket pour suivre le résultat.

        Args:
            event_name: Nom de l'événement.
            priority:   Priorité de l'événement (entier). Si None, utilise -100.
            **params:   Paramètres de l'événement.
        """
        # Créer le ticket avec une copie des params (sans _bridge_ticket)
        ticket_id = f"sch-{uuid.uuid4().hex[:8]}"
        ticket = Ticket(
            id=ticket_id,
            event_name=event_name,
            params=params.copy(),
            submitted_at=time.time(),
        )
        with self._lock:
            self._tickets[ticket_id] = ticket
        self._log_ticket("created", ticket)

        # Créer les paramètres de l'événement avec le ticket injecté
        event_params = params.copy()
        event_params["_bridge_ticket"] = ticket_id

        from fsdeploy.lib.scheduler.model.event import BridgeEvent
        event_priority = -100 if priority is None else priority
        event = BridgeEvent(
            name=event_name,
            params=event_params,
            source="bridge",
            priority=event_priority,
        )
        scheduler = self._get_scheduler()
        if scheduler is not None and hasattr(scheduler, "event_queue"):
            scheduler.event_queue.put(event)
            return ticket_id
        else:
            # Fallback via le bus d'événements
            if self._event_bus is not None:
                self._event_bus.emit("bridge.event", {
                    "name": event_name,
                    "params": event_params,
                    "source": "bridge",
                    "priority": event_priority,
                    "_bridge_ticket": ticket_id,
                })
                logging.warning(
                    "Scheduler non disponible, événement émis via le bus d'événements",
                    extra={"event_name": event_name, "ticket_id": ticket_id}
                )
            else:
                logging.error(
                    "Scheduler non disponible et bus d'événements absent",
                    extra={"event_name": event_name, "ticket_id": ticket_id}
                )
            return ticket_id

    # ═══════════════════════════════════════════════════════════════
    # Soumission d'intents
    # ═══════════════════════════════════════════════════════════════

    def submit(self, intent, priority=None) -> str:
        """Soumet un intent au scheduler et retourne un ticket_id."""
        if priority is not None:
            intent.priority = priority

        # Vérifier si un ticket existe déjà dans le contexte
        existing_ticket = getattr(intent, 'context', {}).get('_bridge_ticket')
        if existing_ticket:
            ticket_id = existing_ticket
            # Ne pas créer un nouveau ticket, mais s'assurer qu'il est suivi
            with self._lock:
                if ticket_id not in self._tickets:
                    # Créer un ticket miroir pour le suivi local
                    self._tickets[ticket_id] = Ticket(
                        id=ticket_id,
                        event_name=f"intent.{intent.__class__.__name__}",
                        params=intent.params.copy() if hasattr(intent, 'params') else {},
                        submitted_at=time.time(),
                    )
                    ticket_created = True
                else:
                    ticket_created = False
            if ticket_created:
                self._log_ticket("created", self._tickets[ticket_id])
        else:
            # Créer un nouveau ticket
            ticket_id = f"sch-intent-{uuid.uuid4().hex[:8]}"
            ticket = Ticket(
                id=ticket_id,
                event_name=f"intent.{intent.__class__.__name__}",
                params=intent.params.copy() if hasattr(intent, 'params') else {},
                submitted_at=time.time(),
            )
            with self._lock:
                self._tickets[ticket_id] = ticket
            self._log_ticket("created", ticket)
            # Injecter le ticket dans le contexte de l'intent
            if not hasattr(intent, 'context'):
                intent.context = {}
            intent.context['_bridge_ticket'] = ticket_id

        scheduler = self._get_scheduler()
        if scheduler is not None and hasattr(scheduler, "intent_queue"):
            scheduler.intent_queue.push(intent)
            return ticket_id
        else:
            # Fallback via le bus d'événements
            from fsdeploy.lib.bus.event_bus import MessageBus
            bus = MessageBus.global_instance()
            bus.emit("intent.submitted", {"intent": intent})
            return ticket_id

    # ═══════════════════════════════════════════════════════════════
    # Interrogation de l'état
    # ═══════════════════════════════════════════════════════════════

    def get_scheduler_state(self) -> dict:
        """Retourne l'état actuel du scheduler (events, intents, tasks, etc.)."""
        scheduler = self._get_scheduler()
        if scheduler is not None and hasattr(scheduler, "state_snapshot"):
            try:
                return scheduler.state_snapshot()
            except Exception:
                pass
        # Données de démo (utilisées par GraphViewScreen en fallback)
        import random
        return {
            "event_count": random.randint(0, 5),
            "intent_count": random.randint(0, 3),
            "task_count": random.randint(0, 2),
            "completed_count": random.randint(10, 50),
            "active_task": None,
            "recent_tasks": []
        }

    # ═══════════════════════════════════════════════════════════════
    # Suivi des tickets
    # ═══════════════════════════════════════════════════════════════

    def is_done(self, ticket_id: str) -> bool:
        """Vrai si le ticket est terminé."""
        with self._lock:
            t = self._tickets.get(ticket_id)
            return (not t) or t.status in ("completed", "failed")

    def get_result(self, ticket_id: str) -> Any:
        """Résultat d'un ticket terminé (None si pas prêt)."""
        with self._lock:
            t = self._tickets.get(ticket_id)
            return t.result if t and t.status == "completed" else None

    def get_error(self, ticket_id: str) -> Optional[str]:
        """Erreur d'un ticket en échec."""
        with self._lock:
            t = self._tickets.get(ticket_id)
            return t.error if t and t.status == "failed" else None

    def get_ticket(self, ticket_id: str) -> Optional[Ticket]:
        with self._lock:
            return self._tickets.get(ticket_id)

    def poll(self) -> list[Ticket]:
        """
        Synchronise les tickets avec l'état du runtime.

        Appelé périodiquement pour mettre à jour les tickets à partir
        des tâches terminées ou échouées.
        """
        just_done = []
        runtime = self._get_runtime_state()
        if runtime is None:
            return just_done

        # Obtenir l'objet état (state) du runtime
        state = runtime
        if hasattr(runtime, 'state'):
            state = runtime.state

        with self._lock:
            pending = [(tid, t) for tid, t in self._tickets.items()
                       if t.status == "pending"]

        for ticket_id, ticket in pending:
            finished = self._match_in_state(ticket, state)
            if finished:
                just_done.append(ticket)

        # Déclencher les callbacks hors du lock
        for ticket in just_done:
            self._fire(ticket)

        return just_done

    def _match_in_state(self, ticket: Ticket, state) -> bool:
        """
        Cherche dans state.completed et .failed une tâche dont
        le contexte contient le _bridge_ticket correspondant.
        """
        # state peut avoir des attributs 'completed' et 'failed' (dicts, listes, ou autres)
        try:
            completed = getattr(state, 'completed', {})
            failed = getattr(state, 'failed', {})
        except AttributeError:
            return False

        # Normaliser en séquence itérable d'entrées
        def iter_entries(collection):
            if isinstance(collection, dict):
                return collection.values()
            elif isinstance(collection, (list, tuple, set)):
                return collection
            else:
                return []

        # Chercher dans completed
        for entry in iter_entries(completed):
            if isinstance(entry, dict):
                task = entry.get('task')
                result = entry.get('result')
            else:
                # l'entrée pourrait être directement l'objet Task
                task = entry if hasattr(entry, 'context') else None
                result = None
            if task is None:
                continue
            ctx = getattr(task, 'context', {})
            params = getattr(task, 'params', {})
            ticket_id_from_task = ctx.get('_bridge_ticket') or params.get('_bridge_ticket')
            if ticket_id_from_task == ticket.id:
                with self._lock:
                    ticket.status = "completed"
                    ticket.result = result
                    self._history.append(ticket)
                self._log_ticket("completed", ticket, result=result)
                return True

        # Chercher dans failed
        for entry in iter_entries(failed):
            if isinstance(entry, dict):
                task = entry.get('task')
                error = entry.get('error')
            else:
                task = entry if hasattr(entry, 'context') else None
                error = None
            if task is None:
                continue
            ctx = getattr(task, 'context', {})
            params = getattr(task, 'params', {})
            ticket_id_from_task = ctx.get('_bridge_ticket') or params.get('_bridge_ticket')
            if ticket_id_from_task == ticket.id:
                with self._lock:
                    ticket.status = "failed"
                    ticket.error = str(error if error is not None else 'unknown')
                    self._history.append(ticket)
                self._log_ticket("failed", ticket, error=error)
                return True

        return False

    def _fire(self, ticket: Ticket) -> None:
        """Déclenche les callbacks d'un ticket."""
        with self._lock:
            cbs = list(ticket.callbacks)
            ticket.callbacks.clear()
        for cb in cbs:
            try:
                cb(ticket)
            except Exception:
                pass

    def on_result(self, ticket_id: str, callback: Callable) -> None:
        """Ajoute un callback à un ticket existant."""
        with self._lock:
            t = self._tickets.get(ticket_id)
            if not t:
                return
            t.callbacks.append(callback)
            # Si déjà terminé, déclencher immédiatement
            if t.status in ("completed", "failed"):
                self._fire(t)

    def wait_for_ticket(self, ticket_id: str, timeout: float | None = None) -> bool:
        """
        Attend que le ticket soit terminé (completed ou failed).

        Args:
            ticket_id: Identifiant du ticket.
            timeout:   Délai maximal d'attente en secondes (None = infini).

        Returns:
            True si le ticket est terminé avant le timeout, False sinon.
        """
        import time
        start = time.time()
        while not self.is_done(ticket_id):
            if timeout is not None and time.time() - start >= timeout:
                return False
            # Mettre à jour les tickets via poll
            self.poll()
            time.sleep(0.1)
        return True

    def get_tickets_by_status(self, status: str) -> list[Ticket]:
        """
        Retourne tous les tickets ayant le statut donné.

        Args:
            status: "pending", "completed" ou "failed".

        Returns:
            Liste des tickets correspondants.
        """
        with self._lock:
            return [t for t in self._tickets.values() if t.status == status]

    # ═══════════════════════════════════════════════════════════════
    # Historique
    # ═══════════════════════════════════════════════════════════════

    @property
    def pending_count(self) -> int:
        with self._lock:
            return sum(1 for t in self._tickets.values()
                       if t.status == "pending")

    @property
    def pending_tickets(self) -> List[Ticket]:
        with self._lock:
            return [t for t in self._tickets.values() if t.status == "pending"]

    @property
    def history(self) -> list[Ticket]:
        with self._lock:
            return list(self._history)

    def clear_done(self) -> int:
        with self._lock:
            to_rm = [k for k, t in self._tickets.items()
                     if t.status in ("completed", "failed")]
            for k in to_rm:
                del self._tickets[k]
            return len(to_rm)

    def cleanup_old(self, max_age_seconds: float = 3600) -> int:
        """
        Supprime les tickets terminés (completed/failed) plus anciens que max_age_seconds.
        Retourne le nombre de tickets supprimés.
        """
        with self._lock:
            to_remove = []
            now = time.time()
            for ticket_id, ticket in self._tickets.items():
                if ticket.status in ("completed", "failed") and \
                   (now - ticket.submitted_at) > max_age_seconds:
                    to_remove.append(ticket_id)
            for ticket_id in to_remove:
                del self._tickets[ticket_id]
            return len(to_remove)

    def reset_tickets(self) -> int:
        """
        Supprime tous les tickets (pending, completed, failed) et retourne
        le nombre total de tickets supprimés.
        """
        with self._lock:
            count = len(self._tickets)
            self._tickets.clear()
            self._history.clear()
            return count

    def get_all_tickets(self) -> List[Ticket]:
        """
        Retourne tous les tickets, quel que soit leur statut.
        """
        with self._lock:
            return list(self._tickets.values())
