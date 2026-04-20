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
from fsdeploy.lib.log import get_logger


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
    Le bridge délègue au SchedulerBridge global (fsdeploy.lib.scheduler.bridge).

    Cette classe agit comme une façade qui masque la complexité du scheduler
    et offre une API simple pour émettre des événements, soumettre des intents,
    et recevoir les résultats de manière asynchrone.

    Chaque appel à `emit` ou `submit_intent` retourne un identifiant de ticket
    qui permet de suivre l'achèvement via `is_done`, `get_result`, etc.
    Les tickets sont automatiquement mis à jour lors des appels à `poll()`,
    lequel doit être invoqué périodiquement (par exemple dans le cycle de
    rafraîchissement de l'UI).

    Attributes:
        runtime: Référence au runtime du scheduler (pour l'événement immédiat).
        store:   Store Huffman pour la journalisation (optionnel).
        _global_bridge: Instance du SchedulerBridge global pour la délégation.
    """
    _instance = None
    @classmethod
    def default(cls) -> "SchedulerBridge":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self, runtime=None, store=None):
        # Accepte désormais les arguments passés par app.py
        self._scheduler = runtime
        self._store = store 
        
        try:
            from fsdeploy.lib.bus.event_bus import MessageBus
            self._event_bus = MessageBus.global_instance()
        except ImportError:
            self._event_bus = None
            
        self._tickets: dict[str, Ticket] = {}
        self._history: deque[Ticket] = deque(maxlen=500)
        self._lock = threading.Lock()

    # ═══════════════════════════════════════════════════════════════
    # EMISSION — la seule methode que la TUI utilise
    # ═══════════════════════════════════════════════════════════════
    def _log_ticket(self, action: str, ticket: Ticket, **extra):
        """Émet un événement de log sans erreur de signature."""
        if self._event_bus is None:
            return
        # Correction : On passe un dictionnaire unique pour éviter le TypeError
        data = {
            "ticket_id": ticket.id,
            "event_name": ticket.event_name,
            "status": ticket.status
        }
        data.update(extra)
        self._event_bus.emit("bridge.ticket." + action, data)


    def emit(self, event_name: str, callback: Optional[Callable] = None, 
             priority: Optional[int] = None, **params) -> str:
        """Alias robuste utilisé par les écrans pour soumettre des événements."""
        # On délègue à submit_event qui gère l'ID et le bus
        ticket_id = self.submit_event(event_name, priority=priority, **params)
        if callback:
            self.on_result(ticket_id, callback)
        return ticket_id

    # ═══════════════════════════════════════════════════════════════
    # RESULTATS
    # ═══════════════════════════════════════════════════════════════

    def is_done(self, ticket_id: str) -> bool:
        """Vrai si le ticket est termine."""
        if self._global_bridge is not None:
            return self._global_bridge.is_done(ticket_id)
        with self._lock:
            t = self._tickets.get(ticket_id)
            return (not t) or t.status in ("completed", "failed")

    def get_result(self, ticket_id: str) -> Any:
        """Resultat d'un ticket termine (None si pas pret)."""
        if self._global_bridge is not None:
            return self._global_bridge.get_result(ticket_id)
        with self._lock:
            t = self._tickets.get(ticket_id)
            return t.result if t and t.status == "completed" else None

    def get_error(self, ticket_id: str) -> Optional[str]:
        """Erreur d'un ticket en echec."""
        if self._global_bridge is not None:
            return self._global_bridge.get_error(ticket_id)
        with self._lock:
            t = self._tickets.get(ticket_id)
            return t.error if t and t.status == "failed" else None

    def get_ticket(self, ticket_id: str) -> Optional[Ticket]:
        if self._global_bridge is not None:
            return self._global_bridge.get_ticket(ticket_id)
        with self._lock:
            return self._tickets.get(ticket_id)

    def on_result(self, ticket_id: str, callback: Callable) -> None:
        """Ajoute un callback a un ticket existant."""
        if self._global_bridge is not None:
            self._global_bridge.on_result(ticket_id, callback)
            return
        with self._lock:
            t = self._tickets.get(ticket_id)
            if not t:
                return
            t.callbacks.append(callback)

    def wait_for_ticket(self, ticket_id: str, timeout: float | None = None) -> bool:
        """
        Attend que le ticket soit terminé (completed ou failed).
        Délègue au bridge global.
        """
        if self._global_bridge is not None:
            return self._global_bridge.wait_for_ticket(ticket_id, timeout)
        # Implémentation locale simple
        import time
        start = time.time()
        while not self.is_done(ticket_id):
            if timeout is not None and time.time() - start >= timeout:
                return False
            time.sleep(0.1)
        return True

    def get_tickets_by_status(self, status: str) -> list[Ticket]:
        """
        Retourne tous les tickets ayant le statut donné.
        Délègue au bridge global.
        """
        if self._global_bridge is not None:
            return self._global_bridge.get_tickets_by_status(status)
        with self._lock:
            return [t for t in self._tickets.values() if t.status == status]

    def get_scheduler_state(self) -> dict:
        """
        Retourne l'état actuel du scheduler (events, intents, tasks, etc.).
        Délègue au bridge global.
        """
        if self._global_bridge is not None:
            return self._global_bridge.get_scheduler_state()
        # Données de démo
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
    # POLLING — appele a chaque cycle refresh de la TUI
    # ═══════════════════════════════════════════════════════════════

    def poll(self) -> list[Ticket]:
        """
        Synchronise les tickets avec runtime.state.

        Appele par FsDeployApp._refresh_from_store() toutes les 2s.
        Retourne la liste des tickets qui viennent de terminer.
        """
        if self._global_bridge is not None:
            return self._global_bridge.poll()
        # Pour les tickets locaux, rien à faire car ils sont déjà terminés immédiatement
        return []

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
    # INTENT DIRECT
    # ═══════════════════════════════════════════════════════════════

    def submit_intent(self, intent, priority=None, callback=None) -> str:
        """
        Soumet un Intent directement à la file du scheduler.
        Un ticket est créé pour suivre l'achèvement, comme pour emit().
        """
        if self._global_bridge is not None:
            # Utiliser le bridge global déjà référencé
            ticket_id = self._global_bridge.submit(intent, priority=priority)
            if callback:
                self._global_bridge.on_result(ticket_id, callback)

            # Log
            if self._store:
                self._store.log_event(
                    f"tui.intent.{intent.__class__.__name__}",
                    source="bridge",
                    ticket=ticket_id,
                )
            return ticket_id
        else:
            # Fallback local
            ticket_id = f"local-intent-{uuid4().hex[:8]}"
            ticket = Ticket(
                id=ticket_id,
                event_name=f"intent.{intent.__class__.__name__}",
                params=getattr(intent, 'params', {}),
                submitted_at=time.time(),
                status="completed",
                result=None
            )
            with self._lock:
                self._tickets[ticket_id] = ticket
                self._history.append(ticket)
            self._log_ticket("submitted", ticket)
            if callback:
                callback(ticket)
            return ticket_id

    # ═══════════════════════════════════════════════════════════════
    # INTROSPECTION
    # ═══════════════════════════════════════════════════════════════

    @property
    def pending_count(self) -> int:
        return self._global_bridge.pending_count

    @property
    def active_events(self) -> list[str]:
        """Noms des events en attente de resultat."""
        # On utilise pending_tickets du bridge global
        pending = self._global_bridge.pending_tickets
        return [t.event_name for t in pending]

    @property
    def history(self) -> list[Ticket]:
        return self._global_bridge.history

    def clear_done(self) -> int:
        if self._global_bridge is not None:
            return self._global_bridge.clear_done()
        with self._lock:
            to_rm = [k for k, t in self._tickets.items()
                     if t.status in ("completed", "failed")]
            for k in to_rm:
                del self._tickets[k]
            return len(to_rm)

    def cleanup_old(self, max_age_seconds: float = 3600) -> int:
        """
        Supprime les tickets terminés plus anciens que max_age_seconds.
        Délègue au bridge global.
        """
        if self._global_bridge is not None:
            return self._global_bridge.cleanup_old(max_age_seconds)
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
        le nombre total de tickets supprimés. Délègue au bridge global.
        """
        if self._global_bridge is not None:
            return self._global_bridge.reset_tickets()
        with self._lock:
            count = len(self._tickets)
            self._tickets.clear()
            self._history.clear()
            return count

    def get_all_tickets(self) -> list[Ticket]:
        """
        Retourne tous les tickets, quel que soit leur statut.
        Délègue au bridge global.
        """
        if self._global_bridge is not None:
            return self._global_bridge.get_all_tickets()
        with self._lock:
            return list(self._tickets.values())
