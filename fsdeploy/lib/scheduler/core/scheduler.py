"""
fsdeploy.scheduler.core.scheduler
==================================
Boucle principale du scheduler.

Cycle :
  1. _process_events()  : EventQueue → IntentQueue (via handlers ou event.to_intents())
  2. _process_intents() : Intent → resolve → Tasks → check locks → execute ou wait
  3. _process_waiting() : retry des tasks en attente quand les locks se libèrent

Le Scheduler tourne en boucle infinie (processus racine).
La TUI est un enfant optionnel et jetable.

Threading :
  - Les tasks "default" sont exécutées inline (bloquent le cycle).
  - Les tasks "threaded" sont soumises au ThreadPoolExecutor de l'Executor
    et NE BLOQUENT PAS le cycle. L'Executor gère state + locks via callback.
"""

import signal
import threading
from typing import Optional


class Scheduler:
    """
    Processus racine de fsdeploy.
    """

    def __init__(self, resolver, executor, runtime):
        self.resolver = resolver
        self.executor = executor
        self.runtime = runtime
        self._running = False
        self._stop_event = threading.Event()
        self._tick_interval = 0.1  # secondes entre chaque cycle

        # Hooks extensibles
        self._on_cycle_start: list = []
        self._on_cycle_end: list = []
        self._on_error: list = []

    # ═════════════════════════════════════════════════════════════════
    # LIFECYCLE
    # ═════════════════════════════════════════════════════════════════

    def run(self) -> None:
        """Boucle principale. Bloquante."""
        self._running = True
        self._stop_event.clear()

        # Signaux
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
                self.runtime.intent_queue.put(intent)

    def _event_to_intents(self, event) -> list:
        """
        Convertit un event en intents.
        Ordre de priorité :
          1. event.to_intents() (si l'event sait se convertir)
          2. IntentQueue handlers (event_name → handler)
        """
        # L'event sait se convertir
        if hasattr(event, "to_intents"):
            result = event.to_intents()
            if result:
                return result

        # Handlers enregistrés
        return self.runtime.intent_queue.create_from_event(event)

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

            except PermissionError as e:
                intent.mark_failed(e)
                self.runtime.fail(intent, e)

            except Exception as e:
                intent.mark_failed(e)
                self.runtime.fail(intent, e)

    def _schedule_task(self, task, intent) -> None:
        """
        Résout une task et l'exécute ou la met en attente.

        Le Scheduler ne gère PAS les locks — il les passe à l'Executor
        qui est responsable de :
          - state.start(task)
          - _run_lifecycle(task)
          - state.success(task) / state.fail(task)
          - state.release_locks(locks)
        """
        context = getattr(intent, "context", {})

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
            except Exception:
                # Sécurité : si execute() elle-même échoue (pas la task),
                # on libère les locks manuellement
                self.runtime.state.release_locks(locks)
        else:
            # Pas de locks disponibles — mise en attente
            task._pending_locks = locks
            self.runtime.add_waiting(task)

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
                self.runtime.fail(task, e)

    # ═════════════════════════════════════════════════════════════════
    # SIGNAUX
    # ═════════════════════════════════════════════════════════════════

    def _handle_signal(self, signum, frame) -> None:
        from scheduler.model.event import SignalEvent
        import signal as sig

        signame = sig.Signals(signum).name
        self.runtime.event_queue.put(
            SignalEvent(signum=signum, signame=signame)
        )

        if signum in (signal.SIGTERM, signal.SIGINT):
            self.stop()

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

    def status(self) -> dict:
        """Résumé de l'état du scheduler."""
        return {
            "running": self._running,
            "state": self.runtime.summary(),
            "executor_pending": self.executor.pending_count,
            "executor_pending_ids": self.executor.pending_ids,
        }
