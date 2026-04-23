"""
fsdeploy.scheduler.core.scheduler
==================================
Boucle principale du scheduler.

Cycle :
  1. _process_events()  : EventQueue → IntentQueue (via handlers ou event.to_intents())
  2. _process_intents() : Intent → resolve → Tasks → check locks → execute ou wait
  3. _process_waiting() : retry des tasks en attente quand les locks se libèrent

Le Scheduler peut tourner dans le main thread (mode daemon/bare)
ou dans un thread background (mode TUI — Textual prend le main thread).

Threading :
  - Les tasks "default" sont exécutées inline (bloquent le cycle).
  - Les tasks "threaded" sont soumises au ThreadPoolExecutor de l'Executor
    et NE BLOQUENT PAS le cycle. L'Executor gère state + locks via callback.

Flux détaillé :
===============
1. Événements
   - Les événements arrivent via `runtime.event_queue.put(event)`.
   - `_process_events()` dépile chaque événement et le convertit en intents.
     a) Si l'événement possède une méthode `to_intents()`, celle-ci est utilisée.
     b) Sinon, les handlers enregistrés dans `runtime.intent_queue` sont consultés
        via `create_from_event(event)` (si disponible) pour produire les intents.
   - Chaque intent est ajouté à `runtime.intent_queue`.

2. Intents
   - `_process_intents()` dépile un intent et appelle `intent.resolve()`.
   - `resolve()` invoque `build_tasks()` de l'intent pour obtenir une liste de tasks.
   - Chaque task est soumise à `_schedule_task()`.
   - Le `Resolver` (`self.resolver`) est utilisé pour déterminer les locks requis
     et résoudre les dépendances (contexte de sécurité, ressources).
   - Si les locks sont disponibles (`runtime.can_run(locks)`), ils sont acquis via
     `runtime.state.acquire_locks(locks)` et la task est passée à l'`Executor`
     via `self.executor.execute(task, locks=locks)`.
   - Si les locks ne sont pas disponibles, la task est placée dans `runtime.waiting_queue`
     avec ses locks en attente (`task._pending_locks`).

3. Exécution des tasks
   - L'`Executor` reçoit la task et décide de l'exécuter immédiatement (mode "default")
     ou de la soumettre à un thread pool (mode "threaded").
   - Pour les tasks "default", `executor.execute()` appelle directement `task.run()`
     (ou son cycle de vie `before_run`/`run`/`after_run`). L'exécution est synchrone.
   - Pour les tasks "threaded", la task est envoyée à un `ThreadPoolExecutor` ; l'`Executor`
     enregistre un callback qui sera notifié à la fin de l'exécution pour mettre à jour
     l'état et libérer les locks.

4. Gestion de l'attente
   - À chaque cycle, `_process_waiting()` examine les tasks en attente.
   - Si pour une task les locks deviennent disponibles, elle est retirée de la file d'attente,
     les locks sont acquis, et la task est confiée à l'`Executor` comme ci-dessus.

5. Gestion des erreurs
   - Toute exception levée pendant le traitement d'un intent ou d'une task est capturée
     et les hooks `_on_error` sont appelés.
   - L'intent ou la task est marqué(e) comme `failed` et les locks éventuellement acquis
     sont libérés.

6. Signaux
   - Si le scheduler tourne dans le thread principal, les signaux SIGTERM et SIGINT
     sont interceptés et convertis en `SignalEvent` placés dans la file d'événements.
     Cela permet un arrêt propre via `stop()`.

Le scheduler expose des hooks (`on_cycle_start`, `on_cycle_end`, `on_error`) pour
l'observation et l'extension.
"""

import signal
import threading
import time
from typing import Optional


def _is_main_thread() -> bool:
    """Retourne True si on est dans le thread principal."""
    return threading.current_thread() is threading.main_thread()


class Scheduler:
    """
    Boucle principale du scheduler fsdeploy.
    """
    _global_instance = None  # Ajouter

    @classmethod
    def global_instance(cls):
        if cls._global_instance is None:
            from fsdeploy.lib.scheduler.core.resolver import Resolver
            from fsdeploy.lib.scheduler.core.executor import Executor
            from fsdeploy.lib.scheduler.core.runtime import Runtime
            from fsdeploy.lib.scheduler.security.resolver import SecurityResolver
            security_resolver = SecurityResolver()
            rt = Runtime()
            resolver = Resolver(security_resolver=security_resolver)
            executor = Executor(runtime=rt)
            cls._global_instance = cls(resolver, executor, rt)
        return cls._global_instance

    @classmethod
    def set_global_instance(cls, instance):
        cls._global_instance = instance

    @classmethod
    def default(cls):
        """Alias pour global_instance."""
        return cls.global_instance()
      
    def __init__(self, resolver, executor, runtime, config=None):
        self.resolver = resolver
        self.executor = executor
        self.runtime = runtime
        self.config = config
        self._running = False
        self._stop_event = threading.Event()
        self._tick_interval = 0.1  # secondes entre chaque cycle

        # Ajouter le ConfigRunner
        self._config_runner = None
        if config:
            try:
                from .config_runner import ConfigRunner
                self._config_runner = ConfigRunner(config)
            except ImportError:
                pass
        
        # Bridge pour l'émission de logs
        self._bridge = None
        
        # Hooks extensibles
        self._on_cycle_start: list = []
        self._on_cycle_end: list = []
        self._on_error: list = []

    # ═════════════════════════════════════════════════════════════════
    # LIFECYCLE
    # ═════════════════════════════════════════════════════════════════

    def run(self) -> None:
        """
        Boucle principale. Bloquante.

        Les signal handlers ne sont installés QUE si le scheduler
        tourne dans le main thread. En mode TUI, le scheduler tourne
        dans un thread background et les signaux sont gérés par
        le daemon (main thread → Textual → SIGTSTP/SIGWINCH).
        """
        self._running = True
        self._stop_event.clear()

        # Signaux — uniquement dans le main thread
        if _is_main_thread():
            signal.signal(signal.SIGTERM, self._handle_signal)
            signal.signal(signal.SIGINT, self._handle_signal)

        while self._running and not self._stop_event.is_set():
            try:
                for hook in self._on_cycle_start:
                    hook(self)

                self._process_events()
                self._process_intents()
                self._process_waiting()

                for hook in self._on_cycle_end:
                    hook(self)

            except Exception as e:
                for hook in self._on_error:
                    hook(self, e)

            self._stop_event.wait(self._tick_interval)

    def stop(self) -> None:
        """Arrête proprement la boucle."""
        self._running = False
        self._stop_event.set()
        # Nettoyage de la cage et des processus
        self._cleanup_all()

    def _cleanup_all(self) -> None:
        """Nettoie la cage chroot et termine les processus actifs."""
        # Arrêter tous les processus du runner
        try:
            from fsdeploy.lib.scheduler.runner import get_runner
            runner = get_runner()
            for proc in runner.get_active_processes():
                runner.kill_process(proc["process_id"])
        except Exception:
            pass
        # Nettoyer les montages de la cage
        try:
            from fsdeploy.lib.scheduler.cage import cleanup_cage
            cleanup_cage()
        except Exception:
            pass

    def run_once(self) -> None:
        """Exécute un seul cycle (utile pour les tests)."""
        self._process_events()
        self._process_intents()
        self._process_waiting()

    # ═════════════════════════════════════════════════════════════════
    # EVENTS → INTENTS
    # ═════════════════════════════════════════════════════════════════

    def _process_events(self) -> None:
        while not self.runtime.event_queue.empty():
            event = self.runtime.event_queue.get()
            if event is None:
                continue

            # Gérer les événements d'authentification
            if event.name == "auth.sudo_response":
                self._handle_sudo_response(event)
                continue
            elif event.name == "auth.sudo_request":
                # Transmettre au bridge UI
                self._forward_sudo_request(event)
                continue

            # Les événements task.completed/task.failed servent uniquement
            # à réveiller _process_waiting au prochain cycle — pas besoin
            # de les convertir en intents.
            if event.name in ("task.completed", "task.failed"):
                continue

            intents = self._event_to_intents(event)

            for intent in intents:
                # Propager le contexte de l'événement
                if not intent.context.get("event"):
                    intent.context["event"] = event
                # Injecter la configuration dans le contexte de l'intent
                if self.config and "config" not in intent.context:
                    intent.context["config"] = self.config
                self.runtime.intent_queue.put(intent)

    def _event_to_intents(self, event) -> list:
        """
        Convertit un event en intents.
        Ordre de priorité :
          1. event.to_intents() (si l'event sait se convertir)
          2. IntentQueue handlers (event_name → handler)
          3. Aucun intent → liste vide
        """
        # L'event sait se convertir
        if hasattr(event, "to_intents"):
            result = event.to_intents()
            if result:
                return result

        # Handlers enregistrés
        if hasattr(self.runtime.intent_queue, 'create_from_event'):
            intents = self.runtime.intent_queue.create_from_event(event)
            if intents is not None:
                return intents
        # Fallback
        return []

    # ═════════════════════════════════════════════════════════════════
    # INTENTS → TASKS → EXECUTION
    # ═════════════════════════════════════════════════════════════════

    def _process_intents(self) -> None:
        while not self.runtime.intent_queue.empty():
            intent = self.runtime.intent_queue.get()
            if intent is None:
                continue

            try:
                intent.set_status("running")

                # Validation
                if hasattr(intent, "validate") and not intent.validate():
                    intent.set_status("failed")
                    continue

                # Résolution : intent → tasks
                tasks = intent.resolve()

                for task in tasks:
                    self._schedule_task(task, intent)

                intent.set_status("completed")

            except Exception as e:
                intent.mark_failed(e)
                # Notifier le runtime si la méthode fail existe
                if hasattr(self.runtime, 'fail'):
                    self.runtime.fail(intent, e)
                # Sinon, simplement journaliser l'erreur
                # (l'erreur est déjà capturée par les hooks via on_error)

    def _schedule_task(self, task, intent) -> None:
        """
        Résout une task et l'exécute ou la met en attente.

        Étapes :
          1. Résolution via `self.resolver.resolve(task, context=intent.context)`
             pour obtenir les locks requis et les ressources.
          2. Vérification de la disponibilité des locks via `self.runtime.can_run(locks)`.
          3. Si les locks sont disponibles :
               a) Acquisition via `self.runtime.state.acquire_locks(locks)`.
               b) Injection du runtime dans la task (`task.set_runtime(self.runtime)`).
               c) Déléguer à l'Executor (`self.executor.execute(task, locks=locks)`).
             Sinon :
               a) Les locks sont stockés dans `task._pending_locks`.
               b) La task est placée dans la file d'attente (`self.runtime.add_waiting(task)`).

        Le Scheduler ne gère PAS les locks — il les passe à l'Executor
        qui est responsable de :
          - state.start(task)
          - _run_lifecycle(task)
          - state.success(task) / state.fail(task)
          - state.release_locks(locks)
        """
        context = getattr(intent, "context", {})
        ticket_id = context.get('_bridge_ticket')

        # Émettre un log de début de tâche
        task_name = task.__class__.__name__ if hasattr(task, '__class__') else "Tâche inconnue"
        self.emit_log(
            f"Début de la tâche: {task_name}",
            ticket_id=ticket_id,
            level="info"
        )

        result = self.resolver.resolve(task, context=context)
        locks = result.get("locks", [])

        if self.runtime.can_run(locks):
            # Acquérir les locks AVANT de passer à l'executor
            self.runtime.state.acquire_locks(locks)

            # Injecter le runtime
            task.set_runtime(self.runtime)

            # Déléguer entièrement à l'executor
            # Pour "default" : synchrone, retourne après fin
            # Pour "threaded" : retourne immédiatement
            try:
                self.executor.execute(task, locks=locks)
                # Émettre un log de succès
                self.emit_log(
                    f"Tâche exécutée avec succès: {task_name}",
                    ticket_id=ticket_id,
                    level="success"
                )
            except Exception as e:
                # Émettre un log d'erreur
                self.emit_log(
                    f"Erreur dans la tâche {task_name}: {str(e)}",
                    ticket_id=ticket_id,
                    level="error"
                )
                # Sécurité : si execute() elle-même échoue (pas la task),
                # on libère les locks manuellement
                self.runtime.state.release_locks(locks)
                raise
        else:
            # Pas de locks disponibles — mise en attente
            task._pending_locks = locks
            self.runtime.add_waiting(task)
            # Émettre un log d'attente
            self.emit_log(
                f"Tâche mise en attente: {task_name} (locks non disponibles)",
                ticket_id=ticket_id,
                level="warning"
            )

    # ═════════════════════════════════════════════════════════════════
    # WAITING QUEUE
    # ═════════════════════════════════════════════════════════════════

    def _process_waiting(self) -> None:
        """
        Retry des tasks en attente.

        Appelé à chaque cycle. Les tasks threaded qui terminent émettent
        un événement task.completed qui garantit un cycle de _process_waiting
        même si aucun autre événement n'arrive.
        """
        for task in list(self.runtime.waiting_queue):
            try:
                locks = getattr(task, "_pending_locks", [])

                if self.runtime.can_run(locks):
                    self.runtime.remove_waiting(task)

                    # Acquérir les locks
                    self.runtime.state.acquire_locks(locks)

                    # Injecter le runtime
                    task.set_runtime(self.runtime)

                    # Déléguer à l'executor
                    try:
                        self.executor.execute(task, locks=locks)
                    except Exception:
                        self.runtime.state.release_locks(locks)

            except Exception as e:
                self.runtime.remove_waiting(task)
                if hasattr(self.runtime, 'fail'):
                    self.runtime.fail(task, e)

    # ═════════════════════════════════════════════════════════════════
    # GESTION AUTHENTIFICATION SUDO
    # ═════════════════════════════════════════════════════════════════

    def execute_config_section(self, section_id: str, params=None):
        """
        Exécute une section de configuration.
        
        Args:
            section_id: ID de la section de configuration
            params: Paramètres supplémentaires
            
        Returns:
            Résultat de l'exécution
        """
        if not self._config_runner:
            return {"success": False, "error": "ConfigRunner non initialisé"}
        
        return self._config_runner.execute(section_id, params or {})

    def _handle_sudo_response(self, event) -> None:
        """Traite la réponse d'authentification sudo."""
        password = event.params.get("password")
        if password:
            # Passer le mot de passe à l'executor
            if hasattr(self.executor, 'set_sudo_password'):
                self.executor.set_sudo_password(password)
            # Passer aussi au ConfigRunner
            if self._config_runner:
                self._config_runner.set_sudo_password(password)
            # Notifier que l'authentification a réussi
            self._notify_sudo_auth_success()
    
    def _forward_sudo_request(self, event) -> None:
        """Transmet la demande sudo au bridge UI."""
        # Cette méthode sera implémentée quand nous aurons le bridge UI
        # Pour l'instant, log seulement
        import logging
        logging.info(f"Demande sudo reçue: {event.params}")
    
    def _notify_sudo_auth_success(self) -> None:
        """Notifie que l'authentification sudo a réussi."""
        from scheduler.model.event import Event
        self.runtime.event_queue.put(Event(
            name="auth.sudo_success",
            params={"message": "Authentification sudo réussie"},
            source="scheduler",
            priority=-100,
        ))

    # ═════════════════════════════════════════════════════════════════
    # SIGNAUX
    # ═════════════════════════════════════════════════════════════════

    def _handle_signal(self, signum, frame) -> None:
        from ..model.event import SignalEvent
        import signal as sig

        signame = sig.Signals(signum).name
        self.runtime.event_queue.put(
            SignalEvent(signum=signum, signame=signame)
        )

        if signum in (signal.SIGTERM, signal.SIGINT):
            self.stop()

    # ═════════════════════════════════════════════════════════════════
    # GESTION DES LOGS
    # ═════════════════════════════════════════════════════════════════

    def set_bridge(self, bridge):
        """Définit le bridge pour l'émission de logs."""
        self._bridge = bridge
    
    def emit_log(self, log: str, stream: str = "stdout", 
                 ticket_id: str = None, level: str = "info") -> None:
        """Émet un log via le bridge."""
        if self._bridge and hasattr(self._bridge, 'emit_log'):
            self._bridge.emit_log(log, stream, ticket_id, level)
        # Fallback: log local
        elif level == "error":
            import logging
            logging.error(f"[Scheduler] {log}")
        elif level == "warning":
            import logging
            logging.warning(f"[Scheduler] {log}")
        else:
            import logging
            logging.info(f"[Scheduler] {log}")

    # ═════════════════════════════════════════════════════════════════
    # HOOKS
    # ═════════════════════════════════════════════════════════════════

    def on_cycle_start(self, hook) -> None:
        self._on_cycle_start.append(hook)

    def on_cycle_end(self, hook) -> None:
        self._on_cycle_end.append(hook)

    def on_error(self, hook) -> None:
        self._on_error.append(hook)

    # ═════════════════════════════════════════════════════════════════
    # INTROSPECTION
    # ═════════════════════════════════════════════════════════════════

    def state_snapshot(self) -> dict:
        """Snapshot thread-safe pour GraphView et bridge."""
        rt = self.runtime
        return {
            "event_count": rt.event_queue.qsize() if hasattr(rt, 'event_queue') else 0,
            "intent_count": rt.intent_queue.qsize() if hasattr(rt, 'intent_queue') else 0,
            "task_count": len(rt.state.running) if hasattr(rt, 'state') else 0,
            "completed_count": len(rt.state.completed) if hasattr(rt, 'state') else 0,
            "active_task": self._get_active_task_data(),
            "recent_tasks": self._get_recent_tasks(10),
        }

    def _get_active_task_data(self) -> dict | None:
        running = getattr(self.runtime, 'state', None)
        if not running or not running.running:
            return None
        task_id, info = next(iter(running.running.items()))
        task = info.get("task")
        return {
            "id": task_id,
            "name": task.__class__.__name__ if task else "?",
            "status": "running",
            "duration": time.monotonic() - info.get("started_at", 0),
        }

    def _get_recent_tasks(self, limit: int = 10) -> list[dict]:
        state = getattr(self.runtime, 'state', None)
        if not state:
            return []
        recent = []
        for tid, info in list(state.completed.items())[-limit:]:
            recent.append({
                "id": tid,
                "name": info.get("task", "").__class__.__name__ if info.get("task") else "?",
                "status": "completed",
                "duration": info.get("duration", 0),
            })
        return recent

    def status(self) -> dict:
        """Résumé de l'état du scheduler."""
        return {
            "running": self._running,
            "state": self.runtime.summary(),
            "executor_pending": self.executor.pending_count,
            "executor_pending_ids": self.executor.pending_ids,
        }
