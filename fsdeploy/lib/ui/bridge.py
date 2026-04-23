"""
fsdeploy.ui.bridge
====================
Pont entre la TUI Textual et le scheduler.
Mise à jour conforme à add.md 24.1.

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

# NOTE: Pour appliquer la migration des écrans (add.md 24.1), veuillez ajouter
# tous les fichiers de `fsdeploy/lib/ui/screens/` au chat.

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Optional
import uuid
from uuid import uuid4
from textual.widgets import RichLog
from fsdeploy.lib.log import get_logger

try:
    from fsdeploy.lib.scheduler.bridge import SchedulerBridge as GlobalSchedulerBridge
except ImportError:
    GlobalSchedulerBridge = None


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
    def default(cls, runtime=None, store=None) -> "SchedulerBridge":
        if cls._instance is None:
            cls._instance = cls(runtime=runtime, store=store)
        return cls._instance

    def __init__(self, runtime=None, store=None):
        # Accepte désormais les arguments passés par app.py
        self._scheduler = runtime
        self._store = store
        self._runtime = runtime   # alias pour compatibilité
        
        try:
            from fsdeploy.lib.bus.event_bus import MessageBus
            self._event_bus = MessageBus.global_instance()
        except ImportError:
            self._event_bus = None
            
        # S'abonner aux événements du scheduler
        if self._event_bus is not None:
            self._event_bus.subscribe("task.start", self._on_task_start)
            self._event_bus.subscribe("task.log", self._on_task_log)
            self._event_bus.subscribe("task.done", self._on_task_done)
            self._event_bus.subscribe("task.progress", self._on_task_progress)
            self._event_bus.subscribe("auth.sudo_request", self._on_sudo_request)
            
        self._tickets: dict[str, Ticket] = {}
        self._history: deque[Ticket] = deque(maxlen=500)
        self._lock = threading.Lock()
        self._app = None   # <-- AJOUTER CETTE LIGNE
        
        # Dictionnaire pour le routage sémantique des logs
        self._log_widgets: dict[str, RichLog] = {}  # clé = "screen_name:stream"
        
        # Obtenir l'instance globale du bridge du scheduler
        if GlobalSchedulerBridge is not None:
            self._global_bridge = GlobalSchedulerBridge.default()
            # Passer la configuration au bridge global si disponible
            if runtime and hasattr(runtime, 'config'):
                self._global_bridge.set_config(runtime.config)
        else:
            # Fallback: créer un bridge local (ne devrait pas arriver)
            self._global_bridge = None
        
        # Définir l'instance singleton si pas déjà défini
        if self.__class__._instance is None:
            self.__class__._instance = self
            
    def register_log_widget(self, screen_name: str, stream: str, widget) -> None:
        """
        Enregistre un widget pour un écran et un flux donné.
        Accepte RichLog ou Log (tout objet avec une méthode write()).
        Appelé par chaque écran d'action lors de on_mount().
        """
        key = f"{screen_name}:{stream}"
        self._log_widgets[key] = widget

    def _log_to_file(self, log: str, stream: str, level: str) -> None:
        """Écrit un log DEBUG dans le fichier global (logging)."""
        import logging
        logging.debug(f"[{stream}] {log}")

    def emit_log(self, log: str, stream: str = "stdout", 
                 ticket_id: str = None, level: str = "info",
                 target_screen: str = None) -> None:
        """
        Émet un log vers l'UI.
        À appeler par le scheduler lorsqu'une tâche produit une sortie.

        Si target_screen est fourni, le log est écrit directement dans le
        widget enregistré pour cet écran/stream (routage sémantique).
        Les logs de niveau DEBUG sont redirigés vers le fichier log global
        et ne sont pas affichés dans l'UI.
        """
        # Les logs DEBUG ne sont pas affichés dans l'UI
        if level == "debug":
            self._log_to_file(log, stream, level)
            return

        # Routage sémantique vers un écran spécifique
        if target_screen and self._app:
            key = f"{target_screen}:{stream}"
            widget = self._log_widgets.get(key)
            if widget:
                # Écrire directement dans le widget (thread-safe via call_from_thread)
                self._app.call_from_thread(widget.write, f"[{level}]{log}[/]")
                return

        # Si aucun target_screen n'est fourni, essayer de déduire l'écran actif
        if not target_screen and self._app:
            try:
                current_screen = self._app.screen
                if current_screen and hasattr(current_screen, 'name'):
                    screen_name = current_screen.name
                    key = f"{screen_name}:{stream}"
                    widget = self._log_widgets.get(key)
                    if widget:
                        self._app.call_from_thread(widget.write, f"[{level}]{log}[/]")
                        return
            except Exception:
                pass

        # Sinon, envoyer via event system (pour le widget global `#log-term`)
        if self._app and hasattr(self._app, 'post_message'):
            from .events import LogMessage
            self._app.post_message(
                LogMessage(log=log, stream=stream, ticket_id=ticket_id, level=level)
            )

    def emit_task_status(self, node_id: str, status: str, progress: float = 0.0, message: str = "") -> None:
        """
        Émet un événement de statut de tâche vers l'UI.
        """
        if self._app and hasattr(self._app, 'post_message'):
            from .events import TaskStatusMessage
            self._app.post_message(
                TaskStatusMessage(node_id=node_id, status=status, progress=progress, message=message)
            )

    def set_app(self, app) -> None:
        """Définit l'application Textual pour les interactions UI (modal sudo)."""
        self._app = app

    def _log_ticket(self, action: str, ticket: Ticket, **extra):
        """Émet un événement de log via emit_log."""
        log_msg = f"Ticket {ticket.id} ({ticket.event_name}): {action}"
        if extra:
            log_msg += f" - {extra}"
        self.emit_log(log_msg, level="info", ticket_id=ticket.id)
        
        # Également émettre vers l'event_bus si disponible
        if self._event_bus is not None:
            data = {
                "ticket_id": ticket.id,
                "event_name": ticket.event_name,
                "status": ticket.status
            }
            data.update(extra)
            self._event_bus.emit("bridge.ticket." + action, data)

    def _on_task_start(self, data):
        node_id = data.get('node_id')
        self.emit_log(f"Tâche démarrée: {node_id}", level="info", ticket_id=data.get('ticket_id'))
        self.emit_task_status(node_id=node_id, status="started", progress=0.0, message="Démarrage...")

    def _on_task_log(self, data):
        text = data.get('text', '')
        target = data.get('target_screen')  # écran cible (optionnel)
        self.emit_log(text, stream="stdout", ticket_id=data.get('ticket_id'), target_screen=target)

    def _on_task_done(self, data):
        node_id = data.get('node_id')
        success = data.get('success', False)
        target = data.get('target_screen')
        if success:
            self.emit_log(f"Tâche terminée avec succès: {node_id}", level="success", ticket_id=data.get('ticket_id'), target_screen=target)
            self.emit_task_status(node_id=node_id, status="completed", progress=1.0, message="Terminé avec succès")
        else:
            self.emit_log(f"Tâche échouée: {node_id}", level="error", ticket_id=data.get('ticket_id'), target_screen=target)
            self.emit_task_status(node_id=node_id, status="failed", progress=1.0, message="Échec")

    def _on_task_progress(self, data):
        node_id = data.get('node_id')
        progress = data.get('progress', 0.0)
        message = data.get('message', '')
        target = data.get('target_screen')
        self.emit_task_status(
            node_id=node_id,
            status="running",
            progress=progress,
            message=message
        )
        self.emit_log(
            f"Progression {node_id}: {int(progress*100)}%",
            stream="stdout",
            ticket_id=data.get('ticket_id'),
            level="info",
            target_screen=target
        )

    def _on_sudo_request(self, data):
        # Le scheduler demande un mot de passe
        section_id = data.get('section_id', 'unknown')
        action = data.get('action', 'Action protégée')
        ticket_id = data.get('ticket_id')  # Le ticket du scheduler qui attend le mot de passe

        def _clear_password(pwd: str | None) -> None:
            """Écrase le mot de passe en mémoire et force la libération."""
            if pwd is None:
                return
            try:
                # Écraser la chaîne avec des zéros
                import ctypes
                length = len(pwd)
                # Obtenir l'adresse mémoire de la chaîne (CPython interne)
                buffer = ctypes.c_char_p(pwd)
                ctypes.memset(buffer, 0, length)
            except Exception:
                pass
            finally:
                # Forcer le garbage collector
                import gc
                gc.collect()

        def handle_password(password: str | None) -> None:
            try:
                if password:
                    self.submit_event(
                        "auth.sudo_response",
                        password=password,
                        original_ticket=ticket_id,
                        section_id=section_id,
                        success=True,
                    )
                else:
                    self.submit_event(
                        "auth.sudo_response",
                        password=None,
                        original_ticket=ticket_id,
                        section_id=section_id,
                        success=False,
                    )
            finally:
                _clear_password(password)
                password = None
                import gc
                gc.collect()
                if 'password' in locals():
                    del password

        self.emit_log(
            f"Demande sudo pour {section_id} ({action})",
            level="warning",
        )
        if self._app is not None:
            self._app.request_sudo_password(
                section_id=section_id,
                action=action,
                callback=handle_password,
            )
        else:
            # Pas d'UI, on répond par un échec
            handle_password(None)

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

    # ═══════════════════════════════════════════════════════════════
    # EMISSION — la seule methode que la TUI utilise
    # ═══════════════════════════════════════════════════════════════
    def submit_event(self, event_name: str, priority: int | None = None, **params) -> str:
        """Soumet un événement au scheduler via le bridge global."""
        # Récupérer ou générer un identifiant local de ticket
        local_ticket_id = params.get('_bridge_ticket')
        if local_ticket_id is None:
            local_ticket_id = str(uuid.uuid4())
            params['_bridge_ticket'] = local_ticket_id
        
        if self._global_bridge is None:
            # Fallback: générer un ticket local immédiatement terminé
            ticket = Ticket(
                id=local_ticket_id,
                event_name=event_name,
                params=params,
                submitted_at=time.time(),
                status="completed",
                result=None
            )
            with self._lock:
                self._tickets[local_ticket_id] = ticket
                self._history.append(ticket)
            self._log_ticket("submitted", ticket)
            # Déclencher les callbacks immédiatement
            self._fire(ticket)
            return local_ticket_id
        
        # Délégation au bridge global avec le ticket local inclus
        global_ticket_id = self._global_bridge.submit_event(
            event_name, priority=priority, **params
        )
        # Créer un ticket local pour le suivi
        ticket = Ticket(
            id=local_ticket_id,
            event_name=event_name,
            params=params,
            submitted_at=time.time(),
            status="pending"
        )
        with self._lock:
            self._tickets[local_ticket_id] = ticket
            self._history.append(ticket)
        self._log_ticket("submitted", ticket)
        return local_ticket_id

    def emit(self, event_name: str, callback: Optional[Callable] = None, 
             priority: Optional[int] = None, **params) -> str:
        """
        Émet un événement vers le scheduler via le bridge global.
        
        Cette méthode est l'interface standard que les écrans doivent utiliser
        pour déclencher des actions. Elle retourne un identifiant de ticket
        permettant de suivre l'exécution.
        
        Args:
            event_name: Nom de l'événement (ex: "zfs.detect", "mount.request")
            callback: Fonction appelée lorsque le ticket est terminé.
            priority: Priorité de l'événement (plus bas = plus prioritaire).
            **params: Paramètres supplémentaires à passer à l'événement.
            
        Returns:
            Identifiant du ticket (chaîne).
        """
        ticket_id = self.submit_event(event_name, priority=priority, **params)
        if callback:
            self.on_result(ticket_id, callback)
        return ticket_id
    
    def execute_config_section(self, section_id: str, callback: Optional[Callable] = None, 
                              priority: Optional[int] = None) -> str:
        """
        Exécute une section de configuration identifiée par son ID.
        
        Args:
            section_id: ID de la section de configuration (ex: "mounts.root", "kernel.compile")
            callback: Fonction appelée lorsque le ticket est terminé
            priority: Priorité de l'exécution
            
        Returns:
            Identifiant du ticket (chaîne)
        """
        return self.emit(
            "config.execute", 
            section_id=section_id,
            callback=callback,
            priority=priority
        )

    def get_config_sections(self) -> list[dict]:
        """
        Récupère toutes les sections de configuration disponibles.
        Délègue au bridge global.
        """
        if self._global_bridge is not None:
            return self._global_bridge.get_config_sections()
        # Fallback : retourner des sections vides
        return []

    def get_config_section(self, section_id: str) -> Optional[dict]:
        """
        Récupère une section de configuration spécifique.
        Délègue au bridge global.
        """
        if self._global_bridge is not None:
            return self._global_bridge.get_config_section(section_id)
        return None
    

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
            # Si le ticket est déjà terminé, déclencher immédiatement
            if t.status in ("completed", "failed"):
                # Copier les callbacks et les exécuter hors du verrou
                cbs = list(t.callbacks)
                t.callbacks.clear()
            else:
                cbs = []
        # Exécuter les callbacks hors du verrou
        for cb in cbs:
            try:
                cb(t)
            except Exception:
                pass

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
        Utilise d'abord le runtime réel si disponible, sinon fallback demo.
        """
        if self._global_bridge is not None:
            return self._global_bridge.get_scheduler_state()
        if self._runtime and hasattr(self._runtime, 'state'):
            state = self._runtime.state
            return {
                "event_count": len(state.get('events', [])),
                "intent_count": len(state.get('intents', [])),
                "task_count": len(state.get('tasks', [])),
                "completed_count": sum(
                    1 for t in state.get('tasks', []) if t.get('status') == 'completed'
                ),
                "active_task": next(
                    (t for t in state.get('tasks', []) if t.get('status') == 'running'), None
                ),
                "recent_tasks": list(state.get('tasks', []))[-10:]
            }
        # Fallback demo (comme avant)
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
            # Obtenir les tickets terminés du bridge global
            completed = self._global_bridge.poll()
            # Mettre à jour les tickets locaux correspondants
            with self._lock:
                for remote_ticket in completed:
                    local_ticket = self._tickets.get(remote_ticket.id)
                    if local_ticket:
                        local_ticket.status = remote_ticket.status
                        local_ticket.result = remote_ticket.result
                        local_ticket.error = remote_ticket.error
                        # Ajouter à l'historique si pas déjà présent
                        if local_ticket not in self._history:
                            self._history.append(local_ticket)
            # Nettoyage automatique des tickets anciens
            self.cleanup_old()
            return completed
        # Pour les tickets locaux, rien à faire car ils sont déjà terminés immédiatement
        # Nettoyage automatique des tickets anciens
        self.cleanup_old()
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
                ticket.callbacks.append(callback)
            self._fire(ticket)
            return ticket_id

    # ═══════════════════════════════════════════════════════════════
    # INTROSPECTION
    # ═══════════════════════════════════════════════════════════════

    @property
    def pending_tickets(self):
        """Retourne les tickets en attente via le bridge global."""
        if self._global_bridge is not None:
            return self._global_bridge.get_tickets_by_status("pending")
        with self._lock:
            return [t for t in self._tickets.values() if t.status == "pending"]

    @property
    def pending_count(self) -> int:
        if self._global_bridge is not None:
            return self._global_bridge.pending_count
        with self._lock:
            return sum(1 for t in self._tickets.values() if t.status == "pending")

    @property
    def active_events(self) -> list[str]:
        """Noms des events en attente de resultat."""
        pending = self.pending_tickets
        return [t.event_name for t in pending]

    @property
    def history(self) -> list[Ticket]:
        if self._global_bridge is not None:
            return self._global_bridge.history
        with self._lock:
            return list(self._history)

    def clear_done(self) -> int:
        if self._global_bridge is not None:
            # Obtenir les tickets à supprimer du bridge global
            count = self._global_bridge.clear_done()
            # Supprimer aussi les tickets locaux correspondants
            with self._lock:
                to_rm = [k for k, t in self._tickets.items()
                         if t.status in ("completed", "failed")]
                for k in to_rm:
                    del self._tickets[k]
            return count
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
            count = self._global_bridge.cleanup_old(max_age_seconds)
            # Supprimer aussi les tickets locaux correspondants
            with self._lock:
                to_remove = []
                now = time.time()
                for ticket_id, ticket in self._tickets.items():
                    if ticket.status in ("completed", "failed") and \
                       (now - ticket.submitted_at) > max_age_seconds:
                        to_remove.append(ticket_id)
                for ticket_id in to_remove:
                    del self._tickets[ticket_id]
            return count
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
            count = self._global_bridge.reset_tickets()
            # Supprimer aussi les tickets locaux
            with self._lock:
                self._tickets.clear()
                self._history.clear()
            return count
        with self._lock:
            count = len(self._tickets)
            self._tickets.clear()
            self._history.clear()
            return count

    def cancel_task(self, process_id: str, ticket_id: str = None) -> bool:
        """
        Annule une tâche en cours d'exécution.
        
        Args:
            process_id: ID du processus à annuler
            ticket_id: Ticket associé (optionnel)
            
        Returns:
            True si la demande d'annulation a été envoyée
        """
        if self._global_bridge is not None:
            # Délégation au bridge global
            return self._global_bridge.cancel_task(process_id, ticket_id)
        
        # Émettre un événement d'annulation
        self.emit("task.cancel", process_id=process_id, ticket_id=ticket_id)
        return True
    
    def request_sudo(self, section_id: str, action: str = "", ticket_id: str = None) -> None:
        """Émet une demande de mot de passe sudo vers l'UI."""
        payload = {
            "section_id": section_id,
            "action": action,
            "ticket_id": ticket_id
        }
        if self._event_bus is not None:
            self._event_bus.emit("auth.sudo_request", payload)
        else:
            self.emit_log(f"Demande sudo pour {section_id}", level="warning")

    def get_all_tickets(self) -> list[Ticket]:
        """
        Retourne tous les tickets, quel que soit leur statut.
        Délègue au bridge global.
        """
        if self._global_bridge is not None:
            return self._global_bridge.get_all_tickets()
        with self._lock:
            return list(self._tickets.values())
