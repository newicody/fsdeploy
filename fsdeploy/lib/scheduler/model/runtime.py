"""
RuntimeState

Source unique de vérité pour l'état du scheduler.

Combine :
  - cycle de vie des tasks   (start / success / fail)
  - gestion des locks         (conflits, parallélisme)
  - file d'attente waiting    (tasks en attente de ressources)

Utilisé par :
  - Executor  → start(), success(), fail()
  - Scheduler → can_run(), add_running(), add_waiting()
  - Runtime   → self.state = RuntimeState()
"""


class RuntimeState:

    def __init__(self):
        # ── Cycle de vie ──────────────────────────────────────────────
        self.running = {}       # id → { task, status, locks }
        self.completed = {}     # id → { task, result, status }
        self.failed = {}        # id → { task, error, status }

        # ── Waiting ───────────────────────────────────────────────────
        self.waiting = {}       # id → task

        # ── Locks actifs ──────────────────────────────────────────────
        self.locks = []         # list[Lock]

    # ═════════════════════════════════════════════════════════════════
    # CYCLE DE VIE (appelé par Executor)
    # ═════════════════════════════════════════════════════════════════

    def start(self, task):
        """Marque une task comme en cours d'exécution."""
        self.running[task.id] = {
            "task": task,
            "status": "running",
        }

    def success(self, task, result):
        """Marque une task comme terminée avec succès."""
        self.running.pop(task.id, None)
        self.completed[task.id] = {
            "task": task,
            "result": result,
            "status": "success",
        }

    def fail(self, task, error):
        """Marque une task comme échouée."""
        self.running.pop(task.id, None)
        self.failed[task.id] = {
            "task": task,
            "error": error,
            "status": "failed",
        }

    def is_running(self, task):
        return task.id in self.running

    # ═════════════════════════════════════════════════════════════════
    # LOCKS ET PARALLÉLISME
    # ═════════════════════════════════════════════════════════════════

    def can_run(self, locks):
        """
        Vérifie qu'aucun lock demandé n'entre en conflit
        avec un lock déjà actif.

        Accepte :
          - une liste de Lock objects  → vérification par conflits()
          - une liste de strings       → toujours True (pas de lock réel)
          - une liste vide             → toujours True
        """
        if not locks:
            return True

        for new_lock in locks:
            # Si c'est un vrai Lock avec .conflicts()
            if hasattr(new_lock, "conflicts"):
                for active_lock in self.locks:
                    if new_lock.conflicts(active_lock):
                        return False
            # Sinon (string, etc.) → pas de blocage
        return True

    def acquire_locks(self, locks):
        """Enregistre des locks comme actifs."""
        for lock in locks:
            if hasattr(lock, "conflicts"):
                self.locks.append(lock)

    def release_locks(self, locks):
        """Libère des locks actifs."""
        for lock in locks:
            try:
                self.locks.remove(lock)
            except ValueError:
                pass

    # ═════════════════════════════════════════════════════════════════
    # RUNNING (avec gestion des locks)
    # ═════════════════════════════════════════════════════════════════

    def add_running(self, task):
        """
        Enregistre une task en cours et acquiert ses locks.
        """
        locks = getattr(task, "locks", [])
        self.start(task)
        self.acquire_locks(locks)

    def remove_running(self, task_id):
        """
        Retire une task du running et libère ses locks.
        """
        entry = self.running.pop(task_id, None)
        if entry:
            task = entry["task"]
            locks = getattr(task, "locks", [])
            self.release_locks(locks)

    # ═════════════════════════════════════════════════════════════════
    # WAITING (tasks en attente de ressources)
    # ═════════════════════════════════════════════════════════════════

    def add_waiting(self, task):
        """Ajoute une task dans la file d'attente."""
        self.waiting[task.id] = task

    def get_waiting(self):
        """Retourne toutes les tasks en attente."""
        return list(self.waiting.values())

    def pop_waiting(self, task_id):
        """Retire et retourne une task de la file d'attente."""
        return self.waiting.pop(task_id, None)

    def remove_waiting(self, task):
        """Retire une task de la file d'attente (par objet)."""
        self.waiting.pop(task.id, None)

    # ═════════════════════════════════════════════════════════════════
    # INTROSPECTION
    # ═════════════════════════════════════════════════════════════════

    @property
    def running_count(self):
        return len(self.running)

    @property
    def completed_count(self):
        return len(self.completed)

    @property
    def failed_count(self):
        return len(self.failed)

    @property
    def waiting_count(self):
        return len(self.waiting)

    def summary(self):
        """Résumé textuel de l'état."""
        return (
            f"running={self.running_count} "
            f"completed={self.completed_count} "
            f"failed={self.failed_count} "
            f"waiting={self.waiting_count} "
            f"locks={len(self.locks)}"
        )
