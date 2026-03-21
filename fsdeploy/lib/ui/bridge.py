"""
fsdeploy.ui.bridge
====================
Pont entre la TUI Textual et le scheduler.

La TUI ne doit JAMAIS :
  - executer de commandes (subprocess)
  - importer des classes de lib/ (Intent, Task, etc.)
  - toucher au runtime.state directement

Tout passe par le bus d'evenements :

  bridge.emit("detection.start", pools=["boot_pool"])
  bridge.emit("mount.request", dataset="boot_pool/boot", mountpoint="/mnt/boot")
  bridge.emit("pool.import", pool="fast_pool")
  bridge.emit("snapshot.create", dataset="tank/home")

Le scheduler convertit ces events en Intents via les handlers enregistres
(@register_intent ou IntentQueue.register_handler). Les Intents produisent
des Tasks. Les Tasks s'executent avec locks, security, logging.

Les resultats reviennent via bridge.poll() qui inspecte runtime.state
en cherchant le _bridge_ticket injecte dans chaque event.

Thread-safe : la TUI et le scheduler tournent dans des threads differents.
"""

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Optional
from uuid import uuid4


@dataclass
class Ticket:
    """Reference a un event soumis au scheduler."""
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
    Interface unique entre la TUI et le scheduler.

    La TUI appelle bridge.emit() — rien d'autre.
    Le bridge met l'event dans l'EventQueue et track le resultat.
    """

    def __init__(self, runtime, store=None):
        """
        Args:
            runtime: scheduler.core.runtime.Runtime (la seule ref partagee)
            store:   intentlog.codec.HuffmanStore (optionnel, pour le log)
        """
        self.runtime = runtime
        self.store = store
        self._lock = threading.Lock()
        self._tickets: dict[str, Ticket] = {}
        self._history: deque[Ticket] = deque(maxlen=500)

    # ═══════════════════════════════════════════════════════════════
    # EMISSION — la seule methode que la TUI utilise
    # ═══════════════════════════════════════════════════════════════

    def emit(self, event_name: str, callback: Callable | None = None,
             **params) -> str:
        """
        Emet un evenement dans le bus du scheduler.

        C'est la SEULE facon pour la TUI de declencher une action.
        Tout le reste est gere par le scheduler (handlers, intents,
        tasks, locks, security).

        Args:
            event_name: Nom de l'evenement.
                        Ex: "detection.start", "mount.request",
                            "pool.import", "snapshot.create",
                            "stream.start", "coherence.check"
            callback:   Appele quand le resultat est disponible.
                        Signature: callback(ticket: Ticket)
            **params:   Parametres de l'evenement.
                        Ex: pools=["boot_pool"], dataset="tank/home"

        Returns:
            ticket_id: str — pour suivre le resultat.

        Exemple dans un ecran :
            tid = self.app.bridge.emit(
                "detection.start",
                pools=["boot_pool", "fast_pool"],
                callback=self._on_detection_done,
            )
        """
        # Creer le ticket
        ticket_id = f"tui-{uuid4().hex[:8]}"
        ticket = Ticket(
            id=ticket_id,
            event_name=event_name,
            params=params,
            submitted_at=time.time(),
        )
        if callback:
            ticket.callbacks.append(callback)

        with self._lock:
            self._tickets[ticket_id] = ticket

        # Injecter le ticket_id dans les params de l'event
        # pour pouvoir le retrouver dans les resultats
        params["_bridge_ticket"] = ticket_id

        # Creer l'event et le pousser dans la queue
        # Import local pour ne pas coupler bridge.py a event.py au top level
        from scheduler.model.event import Event

        event = Event(
            name=event_name,
            params=params,
            source="tui",
            priority=-1,  # prioritaire
        )
        self.runtime.event_queue.put(event)

        # Log dans le store
        if self.store:
            self.store.log_event(
                f"tui.emit.{event_name}",
                source="bridge",
                ticket=ticket_id,
            )

        return ticket_id

    # ═══════════════════════════════════════════════════════════════
    # RESULTATS
    # ═══════════════════════════════════════════════════════════════

    def is_done(self, ticket_id: str) -> bool:
        """Vrai si le ticket est termine."""
        with self._lock:
            t = self._tickets.get(ticket_id)
            return (not t) or t.status in ("completed", "failed")

    def get_result(self, ticket_id: str) -> Any:
        """Resultat d'un ticket termine (None si pas pret)."""
        with self._lock:
            t = self._tickets.get(ticket_id)
            return t.result if t and t.status == "completed" else None

    def get_error(self, ticket_id: str) -> Optional[str]:
        """Erreur d'un ticket en echec."""
        with self._lock:
            t = self._tickets.get(ticket_id)
            return t.error if t and t.status == "failed" else None

    def get_ticket(self, ticket_id: str) -> Optional[Ticket]:
        with self._lock:
            return self._tickets.get(ticket_id)

    def on_result(self, ticket_id: str, callback: Callable) -> None:
        """Ajoute un callback a un ticket existant."""
        with self._lock:
            t = self._tickets.get(ticket_id)
            if not t:
                return
            t.callbacks.append(callback)
            # Si deja termine, fire immediatement
            if t.status in ("completed", "failed"):
                self._fire(t)

    # ═══════════════════════════════════════════════════════════════
    # POLLING — appele a chaque cycle refresh de la TUI
    # ═══════════════════════════════════════════════════════════════

    def poll(self) -> list[Ticket]:
        """
        Synchronise les tickets avec runtime.state.

        Appele par FsDeployApp._refresh_from_store() toutes les 2s.
        Cherche les tasks terminees dont le context contient
        un _bridge_ticket correspondant a un ticket en cours.

        Returns: liste des tickets qui viennent de terminer.
        """
        just_done = []

        with self._lock:
            pending = [(tid, t) for tid, t in self._tickets.items()
                       if t.status == "pending"]

        for ticket_id, ticket in pending:
            finished = self._match_in_state(ticket)
            if finished:
                just_done.append(ticket)

        # Fire callbacks hors du lock
        for ticket in just_done:
            self._fire(ticket)

        return just_done

    def _match_in_state(self, ticket: Ticket) -> bool:
        """
        Cherche dans runtime.state.completed et .failed
        une task/intent dont le context._bridge_ticket matche.
        """
        state = self.runtime.state

        with state._lock:
            # Chercher dans completed
            for task_id, entry in state.completed.items():
                task = entry.get("task")
                ctx = getattr(task, "context", {}) if task else {}
                if ctx.get("_bridge_ticket") == ticket.id:
                    with self._lock:
                        ticket.status = "completed"
                        ticket.result = entry.get("result")
                        self._history.append(ticket)
                    return True

            # Chercher dans failed
            for task_id, entry in state.failed.items():
                task = entry.get("task")
                ctx = getattr(task, "context", {}) if task else {}
                if ctx.get("_bridge_ticket") == ticket.id:
                    with self._lock:
                        ticket.status = "failed"
                        ticket.error = str(entry.get("error", "unknown"))
                        self._history.append(ticket)
                    return True

        return False

    def _fire(self, ticket: Ticket) -> None:
        """Declenche les callbacks d'un ticket."""
        cbs = list(ticket.callbacks)
        ticket.callbacks.clear()
        for cb in cbs:
            try:
                cb(ticket)
            except Exception:
                pass

    # ═══════════════════════════════════════════════════════════════
    # MULTI-TICKET — pour les operations en plusieurs phases
    # ═══════════════════════════════════════════════════════════════

    def emit_sequence(self, events: list[tuple[str, dict]],
                      callback: Callable | None = None) -> list[str]:
        """
        Emet une sequence d'events. Le callback est appele
        quand TOUS les tickets sont termines.

        Args:
            events: [(event_name, params), ...]
            callback: Appele avec la liste des Tickets termines.

        Returns: liste de ticket_ids
        """
        ticket_ids = []
        for name, params in events:
            tid = self.emit(name, **params)
            ticket_ids.append(tid)

        if callback:
            # Enregistrer un watcher qui attend que tout soit done
            def _check_all(t):
                if all(self.is_done(tid) for tid in ticket_ids):
                    tickets = [self.get_ticket(tid) for tid in ticket_ids]
                    callback([t for t in tickets if t])

            # Attacher le check a chaque ticket
            for tid in ticket_ids:
                self.on_result(tid, _check_all)

        return ticket_ids

    # ═══════════════════════════════════════════════════════════════
    # INTROSPECTION
    # ═══════════════════════════════════════════════════════════════

    @property
    def pending_count(self) -> int:
        with self._lock:
            return sum(1 for t in self._tickets.values()
                       if t.status == "pending")

    @property
    def active_events(self) -> list[str]:
        """Noms des events en attente de resultat."""
        with self._lock:
            return [t.event_name for t in self._tickets.values()
                    if t.status == "pending"]

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
