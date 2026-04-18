"""
fsdeploy.scheduler.core.executor
=================================
Exécution des tâches.

Modes :
  - "default"  : synchrone — bloque le cycle du scheduler le temps de la task
  - "threaded" : non-bloquant — soumis au ThreadPoolExecutor, callback à la fin

L'Executor possède entièrement le cycle de vie d'une task :
  start → before_run → run → after_run → success/fail → release locks

Le Scheduler ne touche JAMAIS aux locks ni au state — il délègue à l'Executor.
"""

import threading
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Callable, Optional


class Executor:
    """
    Exécute les tasks du scheduler.

    Le ThreadPoolExecutor est partagé pour toutes les tasks "threaded".
    Les tasks "default" sont exécutées inline dans le thread du scheduler.

    Usage par le Scheduler :
        executor.execute(task, locks=locks)
        # Pour "default" : retourne quand la task est terminée
        # Pour "threaded" : retourne immédiatement, callback gère le reste
    """

    def __init__(self, runtime, max_workers: int = 4):
        self.runtime = runtime
        self._pool = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="fsdeploy-task",
        )
        self.resolver = None
        try:
            from fsdeploy.lib.scheduler.security.resolver import SecurityResolver
            self.resolver = SecurityResolver(config=getattr(runtime, 'config', None))
        except ImportError:
            pass
        self._futures: dict[str, Future] = {}  # task.id → Future
        self._lock = threading.Lock()           # protège _futures
        self._on_complete: list[Callable] = []  # hooks post-exécution

    # ═════════════════════════════════════════════════════════════════
    # ENTRY POINT
    # ═════════════════════════════════════════════════════════════════

    def execute(self, task, locks: list | None = None) -> None:
        """
        Point d'entrée unique.

        Args:
            task:  Task à exécuter (doit avoir .id, .run(), etc.)
            locks: Locks acquis par le Scheduler — l'Executor les libère.

        Pour executor="default" : exécution synchrone, retourne après fin.
        Pour executor="threaded" : soumission au pool, retourne immédiatement.
        """
        if task is None:
            return

        locks = locks or []

        if hasattr(task, "set_runtime"):
            task.set_runtime(self.runtime)

        # Security check
        if self.resolver is not None:
            ctx = {"dry_run": getattr(self.runtime, "dry_run", False)}
            allowed, reason = self.resolver.check(task, ctx)
            if not allowed:
                self.runtime.state.release_locks(locks)
                self.runtime.state.fail(task, Exception(reason))
                self._emit_completion_event(task, error=reason)
                return

        # Marquer la task comme running
        self.runtime.state.start(task)

        executor_type = getattr(task, "executor", "default")

        if executor_type == "threaded":
            self._execute_threaded(task, locks)
        else:
            self._execute_default(task, locks)

    # ═════════════════════════════════════════════════════════════════
    # SYNC — bloque le cycle le temps de la task
    # ═════════════════════════════════════════════════════════════════

    def _execute_default(self, task, locks: list) -> None:
        """Exécution synchrone dans le thread du scheduler."""
        try:
            result = self._run_lifecycle(task)
            self.runtime.state.success(task, result)
        except Exception as e:
            self.runtime.state.fail(task, e)
            self._log_error(task, e)
        finally:
            self.runtime.state.release_locks(locks)
            self._fire_complete(task)

    # ═════════════════════════════════════════════════════════════════
    # ASYNC — soumission au ThreadPoolExecutor, non-bloquant
    # ═════════════════════════════════════════════════════════════════

    def _execute_threaded(self, task, locks: list) -> None:
        """
        Soumission au pool de threads.

        Le scheduler continue son cycle immédiatement.
        Le callback _on_task_done gère :
          - state.success() ou state.fail()
          - release_locks()
          - émission d'événement de complétion
        """
        def _worker() -> Any:
            return self._run_lifecycle(task)

        future = self._pool.submit(_worker)

        with self._lock:
            self._futures[task.id] = future

        # Callback déclenché quand le Future est terminé (dans le thread du pool)
        future.add_done_callback(
            lambda f: self._on_task_done(task, f, locks)
        )

    def _on_task_done(self, task, future: Future, locks: list) -> None:
        """
        Callback post-exécution d'une task threaded.

        Exécuté dans le thread du pool — thread-safe via RuntimeState.
        """
        # Retirer du tracking des futures
        with self._lock:
            self._futures.pop(task.id, None)

        exc = future.exception()
        if exc is not None:
            self.runtime.state.fail(task, exc)
            self._log_error(task, exc)
        else:
            self.runtime.state.success(task, future.result())

        # Libérer les locks — permet aux tasks en attente de s'exécuter
        self.runtime.state.release_locks(locks)

        # Émettre un événement de complétion pour que le scheduler
        # puisse re-process la waiting queue au prochain cycle
        self._emit_completion_event(task, exc)

        # Hooks
        self._fire_complete(task)

    # ═════════════════════════════════════════════════════════════════
    # LIFECYCLE — before_run → run → after_run (sans state tracking)
    # ═════════════════════════════════════════════════════════════════

    def _run_lifecycle(self, task) -> Any:
        """
        Exécute le cycle de vie complet d'une task.

        NE TOUCHE PAS au state (start/success/fail) — c'est le caller
        (_execute_default ou _on_task_done) qui s'en charge.

        Raises:
            Toute exception levée par before_run/run/after_run.
        """
        cgroup = None

        # Setup cgroup si demande par le decorator
        sec_opts = getattr(task.__class__, '_security_options', {})
        cg_cpu = sec_opts.get('cgroup_cpu', 0)
        cg_mem = sec_opts.get('cgroup_mem', 0)
        if cg_cpu or cg_mem:
            try:
                from fsdeploy.lib.scheduler.core.isolation import CgroupLimits
                if CgroupLimits.available():
                    cgroup = CgroupLimits(
                        name=f"task-{task.id}",
                        cpu_percent=int(cg_cpu) if cg_cpu else 100,
                        mem_max_mb=int(cg_mem) if cg_mem else 0,
                    )
                    cgroup.create()
                    task._cgroup = cgroup
            except Exception:
                pass  # cgroup optionnel, on continue sans

        try:
            if hasattr(task, "before_run"):
                task.before_run()

            result = task.run()

            if hasattr(task, "after_run"):
                task.after_run()

            return result
        finally:
            # Cleanup cgroup
            if cgroup is not None:
                try:
                    cgroup.cleanup()
                except Exception:
                    pass
                task._cgroup = None

    # ═════════════════════════════════════════════════════════════════
    # INTROSPECTION
    # ═════════════════════════════════════════════════════════════════

    @property
    def pending_count(self) -> int:
        """Nombre de tasks threaded en cours d'exécution."""
        with self._lock:
            return len(self._futures)

    @property
    def pending_ids(self) -> list[str]:
        """IDs des tasks threaded en cours."""
        with self._lock:
            return list(self._futures.keys())

    def is_pending(self, task_id: str) -> bool:
        """Vrai si la task est en cours dans le pool."""
        with self._lock:
            return task_id in self._futures

    # ═════════════════════════════════════════════════════════════════
    # HOOKS
    # ═════════════════════════════════════════════════════════════════

    def on_complete(self, callback: Callable) -> None:
        """
        Enregistre un hook appelé après chaque task terminée.

        Signature du callback : callback(task)
        """
        self._on_complete.append(callback)

    def _fire_complete(self, task) -> None:
        for hook in self._on_complete:
            try:
                hook(task)
            except Exception:
                pass  # les hooks ne doivent pas casser le flow

    # ═════════════════════════════════════════════════════════════════
    # EVENTS
    # ═════════════════════════════════════════════════════════════════

    def _emit_completion_event(self, task, error: Exception | None) -> None:
        """
        Émet un événement task.completed ou task.failed.

        Permet au scheduler de réveiller les tasks en attente
        quand des locks se libèrent.
        """
        if not hasattr(self.runtime, "event_queue"):
            return

        from scheduler.model.event import Event

        status = "failed" if error else "completed"
        self.runtime.event_queue.put(Event(
            name=f"task.{status}",
            params={
                "task_id": task.id,
                "task_class": task.__class__.__name__,
                "error": str(error) if error else None,
            },
            source="executor",
            priority=-1,  # urgent — traité en priorité au prochain cycle
        ))

    # ═════════════════════════════════════════════════════════════════
    # LOGGING
    # ═════════════════════════════════════════════════════════════════

    def _log_error(self, task, error: Exception) -> None:
        """Log d'erreur via le monitor si disponible."""
        monitor = getattr(self.runtime, "monitor", None)
        if monitor and hasattr(monitor, "log_error"):
            monitor.log_error(task, error)

    # ═════════════════════════════════════════════════════════════════
    # SHUTDOWN
    # ═════════════════════════════════════════════════════════════════

    def shutdown(self, wait: bool = True, timeout: float | None = 30) -> None:
        """
        Arrêt propre du pool de threads.

        Args:
            wait:    Si True, attend la fin des tasks en cours.
            timeout: Timeout max en secondes (None = pas de limite).
        """
        self._pool.shutdown(wait=wait, cancel_futures=not wait)

    def cancel_all(self) -> int:
        """
        Annule toutes les tasks en attente dans le pool.

        Returns:
            Nombre de futures annulées.
        """
        cancelled = 0
        with self._lock:
            for task_id, future in list(self._futures.items()):
                if future.cancel():
                    cancelled += 1
                    self._futures.pop(task_id, None)
        return cancelled
