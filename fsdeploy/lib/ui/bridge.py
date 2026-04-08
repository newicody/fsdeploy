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

    def __init__(self, runtime, store=None):
        """
        Args:
            runtime: scheduler.core.runtime.Runtime (la seule ref partagee)
            store:   intentlog.codec.HuffmanStore (optionnel, pour le log)
        """
        self.runtime = runtime
        self.store = store
        self._lock = threading.Lock()
        # Déléguer la gestion des tickets au SchedulerBridge global
        from fsdeploy.lib.scheduler.bridge import SchedulerBridge as GlobalBridge
        self._global_bridge = GlobalBridge.default()

    # ═══════════════════════════════════════════════════════════════
    # EMISSION — la seule methode que la TUI utilise
    # ═══════════════════════════════════════════════════════════════

    def emit(self, event_name: str, callback: Callable | None = None,
             priority: int | None = None, **params) -> str:
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
            priority:   Priorite de l'evenement (entier). Les valeurs negatives
                        sont traitees avant les positives. Si None, utilise -100.
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
        # Soumettre via le bridge global
        ticket_id = self._global_bridge.submit_event(
            event_name,
            priority=priority,
            **params
        )
        # Ajouter le callback si fourni
        if callback:
            self._global_bridge.on_result(ticket_id, callback)

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
        return self._global_bridge.is_done(ticket_id)

    def get_result(self, ticket_id: str) -> Any:
        """Resultat d'un ticket termine (None si pas pret)."""
        return self._global_bridge.get_result(ticket_id)

    def get_error(self, ticket_id: str) -> Optional[str]:
        """Erreur d'un ticket en echec."""
        return self._global_bridge.get_error(ticket_id)

    def get_ticket(self, ticket_id: str) -> Optional[Ticket]:
        return self._global_bridge.get_ticket(ticket_id)

    def on_result(self, ticket_id: str, callback: Callable) -> None:
        """Ajoute un callback a un ticket existant."""
        self._global_bridge.on_result(ticket_id, callback)

    def wait_for_ticket(self, ticket_id: str, timeout: float | None = None) -> bool:
        """
        Attend que le ticket soit terminé (completed ou failed).
        Délègue au bridge global.
        """
        return self._global_bridge.wait_for_ticket(ticket_id, timeout)

    def get_tickets_by_status(self, status: str) -> list[Ticket]:
        """
        Retourne tous les tickets ayant le statut donné.
        Délègue au bridge global.
        """
        return self._global_bridge.get_tickets_by_status(status)

    def get_scheduler_state(self) -> dict:
        """
        Retourne l'état actuel du scheduler (events, intents, tasks, etc.).
        Délègue au bridge global.
        """
        return self._global_bridge.get_scheduler_state()

    # ═══════════════════════════════════════════════════════════════
    # POLLING — appele a chaque cycle refresh de la TUI
    # ═══════════════════════════════════════════════════════════════

    def poll(self) -> list[Ticket]:
        """
        Synchronise les tickets avec runtime.state.

        Appele par FsDeployApp._refresh_from_store() toutes les 2s.
        Retourne la liste des tickets qui viennent de terminer.
        """
        return self._global_bridge.poll()

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
        # Utiliser le bridge global déjà référencé
        ticket_id = self._global_bridge.submit(intent, priority=priority)
        if callback:
            self._global_bridge.on_result(ticket_id, callback)

        # Log
        if self.store:
            self.store.log_event(
                f"tui.intent.{intent.__class__.__name__}",
                source="bridge",
                ticket=ticket_id,
            )

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
        return self._global_bridge.clear_done()

    def cleanup_old(self, max_age_seconds: float = 3600) -> int:
        """
        Supprime les tickets terminés plus anciens que max_age_seconds.
        Délègue au bridge global.
        """
        return self._global_bridge.cleanup_old(max_age_seconds)

    def reset_tickets(self) -> int:
        """
        Supprime tous les tickets (pending, completed, failed) et retourne
        le nombre total de tickets supprimés. Délègue au bridge global.
        """
        return self._global_bridge.reset_tickets()

    def get_all_tickets(self) -> list[Ticket]:
        """
        Retourne tous les tickets, quel que soit leur statut.
        Délègue au bridge global.
        """
        return self._global_bridge.get_all_tickets()
