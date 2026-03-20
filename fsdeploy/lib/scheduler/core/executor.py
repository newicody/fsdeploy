"""
fsdeploy.scheduler.core.executor
=================================
Exécution des tâches.

L'Executor ne gère PAS la sécurité, les locks ou les ressources.
Il exécute le cycle : before_run → run → after_run avec tracking d'état.
"""

import threading
from typing import Any, Optional


class Executor:

    def __init__(self, runtime):
        self.runtime = runtime

    # ═════════════════════════════════════════════════════════════════
    # ENTRY POINT
    # ═════════════════════════════════════════════════════════════════

    def execute(self, task) -> Any:
        """
        Point d'entrée. Dispatch vers le mode d'exécution approprié.
        """
        if task is None:
            return None

        if hasattr(task, "set_runtime"):
            task.set_runtime(self.runtime)

        executor_type = getattr(task, "executor", "default")

        if executor_type == "default":
            return self._execute_default(task)
        elif executor_type == "threaded":
            return self._execute_threaded(task)
        else:
            raise ValueError(f"Unknown executor type: {executor_type}")

    # ═════════════════════════════════════════════════════════════════
    # MODES D'EXÉCUTION
    # ═════════════════════════════════════════════════════════════════

    def _execute_default(self, task) -> Any:
        """Exécution synchrone directe."""
        return self._run_task(task)

    def _execute_threaded(self, task) -> Any:
        """Exécution dans un thread dédié."""
        result_holder: dict[str, Any] = {}
        error_holder: list[Exception] = []

        def target():
            try:
                result_holder["value"] = self._run_task(task)
            except Exception as e:
                error_holder.append(e)

        thread = threading.Thread(target=target, daemon=True)
        thread.start()
        thread.join()

        if error_holder:
            raise error_holder[0]
        return result_holder.get("value")

    # ═════════════════════════════════════════════════════════════════
    # CORE TASK EXECUTION
    # ═════════════════════════════════════════════════════════════════

    def _run_task(self, task) -> Any:
        """
        Cycle complet :
          1. start tracking
          2. before_run hook
          3. run (exécution réelle)
          4. after_run hook
          5. success tracking

        En cas d'erreur → fail tracking + re-raise.
        """
        self.runtime.state.start(task)

        try:
            if hasattr(task, "before_run"):
                task.before_run()

            result = task.run()

            if hasattr(task, "after_run"):
                task.after_run()

            self.runtime.state.success(task, result)
            return result

        except Exception as e:
            self.runtime.state.fail(task, e)

            if hasattr(self.runtime, "monitor") and self.runtime.monitor:
                self.runtime.monitor.log_error(task, e)

            raise
