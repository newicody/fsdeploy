"""
Executor

Responsable de l'exécution des tâches.

Fonctions :
  - lancer les tâches (sync / thread)
  - gérer le cycle before_run → run → after_run
  - tracker le résultat via RuntimeState
  - gérer les erreurs

L'Executor ne gère PAS :
  - la sécurité        → Resolver
  - les locks          → RuntimeState
  - les ressources     → RuntimeState
"""


class Executor:

    def __init__(self, runtime):
        self.runtime = runtime

    # ═════════════════════════════════════════════════════════════════
    # ENTRY POINT
    # ═════════════════════════════════════════════════════════════════

    def execute(self, task):
        """
        Point d'entrée principal.
        Dispatch vers le mode d'exécution approprié.
        """
        if task is None:
            return None

        # Attacher runtime si nécessaire
        if hasattr(task, "set_runtime"):
            task.set_runtime(self.runtime)

        # Choix du mode d'exécution
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

    def _execute_default(self, task):
        """Exécution synchrone directe."""
        return self._run_task(task)

    def _execute_threaded(self, task):
        """Exécution dans un thread dédié."""
        import threading

        result = {}

        def target():
            result["value"] = self._run_task(task)

        thread = threading.Thread(target=target)
        thread.start()
        thread.join()

        return result.get("value")

    # ═════════════════════════════════════════════════════════════════
    # CORE TASK EXECUTION
    # ═════════════════════════════════════════════════════════════════

    def _run_task(self, task):
        """
        Exécute le cycle complet d'une task :
          1. start tracking
          2. before_run hook
          3. run (exécution réelle)
          4. after_run hook
          5. success tracking

        En cas d'erreur → fail tracking + re-raise.
        """
        # START tracking
        self.runtime.state.start(task)

        try:
            # BEFORE HOOK
            if hasattr(task, "before_run"):
                task.before_run()

            # EXECUTION
            result = task.run()

            # AFTER HOOK
            if hasattr(task, "after_run"):
                task.after_run()

            # SUCCESS
            self.runtime.state.success(task, result)

            return result

        except Exception as e:
            # FAILURE
            self.runtime.state.fail(task, e)

            # Logging si dispo
            if hasattr(self.runtime, "monitor"):
                self.runtime.monitor.log(f"Task failed: {task} -> {e}")

            raise
