"""
Executor

Responsable de l'exécution des tâches.

Fonctions :

- résoudre les règles de sécurité (via resolver)
- vérifier les locks (via runtime state)
- lancer les tâches (sync / thread / async)
- gérer les erreurs
- gérer le cancel / reprise

C'est le moteur d'exécution du scheduler.
"""
class Executor:

    def __init__(self, runtime):
        self.runtime = runtime

    # -------------------------
    # ENTRY POINT
    # -------------------------
    def execute(self, task):

        if task is None:
            return None

        # Attacher runtime si nécessaire
        if hasattr(task, "set_runtime"):
            task.set_runtime(self.runtime)

        # Choix du mode d’exécution
        executor_type = getattr(task, "executor", "default")

        if executor_type == "default":
            return self._execute_default(task)

        elif executor_type == "threaded":
            return self._execute_threaded(task)

        else:
            raise ValueError(f"Unknown executor type: {executor_type}")

    # -------------------------
    # DEFAULT EXECUTION
    # -------------------------
    def _execute_default(self, task):
        return self._run_task(task)

    # -------------------------
    # THREADED EXECUTION
    # -------------------------
    def _execute_threaded(self, task):
        import threading

        result = {}

        def target():
            result["value"] = self._run_task(task)

        thread = threading.Thread(target=target)
        thread.start()
        thread.join()

        return result.get("value")

    # -------------------------
    # CORE TASK EXECUTION
    # -------------------------
    def _run_task(self, task):

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

    def _resolve(self, intent):
        """
        Résout les règles de sécurité.
        """
        pass

    def _can_run(self, resources):
        """
        Vérifie si les ressources sont disponibles.
        """
        pass

    def _lock(self, locks):
        """
        Applique les verrous.
        """
        pass

    def _unlock(self, locks):
        """
        Libère les verrous.
        """
        pass

    def _run_task(self, intent):
        """
        Lance réellement la tâche.

        Peut utiliser :
        - direct (sync)
        - thread
        - asyncio
        """
        pass

    def _handle_error(self, intent, error):
        """
        Gestion des erreurs d'exécution.
        """
        pass

    def cancel(self, intent_id):
        """
        Annule une tâche en cours.
        """
        pass


    def resume(self, intent):
        """
        Reprend une tâche.
        """
        pass
