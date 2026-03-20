"""
fsdeploy.scheduler.model.runtime
=================================
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

import time
from typing import Any, Optional


class RuntimeState:

    def __init__(self):
        # ── Cycle de vie ──────────────────────────────────────────────
        self.running: dict[str, dict] = {}       # id → {task, status, started_at}
        self.completed: dict[str, dict] = {}     # id → {task, result, status, duration}
        self.failed: dict[str, dict] = {}        # id → {task, error, status, duration}

        # ── Waiting ───────────────────────────────────────────────────
        self.waiting: dict[str, Any] = {}        # id → task (O(1) access)

        # ── Locks actifs ──────────────────────────────────────────────
        self.locks: list = []                    # list[Lock]

    # ═════════════════════════════════════════════════════════════════
    # CYCLE DE VIE (appelé par Executor)
    # ═════════════════════════════════════════════════════════════════

    def start(self, task) -> None:
        """Marque une task comme en cours d'exécution."""
        self.running[task.id] = {
            "task": task,
            "status": "running",
            "started_at": time.monotonic(),
        }

    def success(self, task, result=None) -> None:
        """Marque une task comme terminée avec succès."""
        entry = self.running.pop(task.id, None)
        started = entry["started_at"] if entry else 0
        self.completed[task.id] = {
            "task": task,
            "result": result,
            "status": "success",
            "duration": time.monotonic() - started,
        }

    def fail(self, task, error: Exception | str = None) -> None:
        """Marque une task comme échouée."""
        entry = self.running.pop(task.id, None)
        started = entry["started_at"] if entry else 0
        self.failed[task.id] = {
            "task": task,
            "error": error,
            "status": "failed",
            "duration": time.monotonic() - started,
        }

    def is_running(self, task) -> bool:
        return task.id in self.running

    # ═════════════════════════════════════════════════════════════════
    # LOCKS ET PARALLÉLISME
    # ═════════════════════════════════════════════════════════════════

    def can_run(self, locks) -> bool:
        """
        Vérifie qu'aucun lock demandé ne conflicte avec un lock actif.

        Accepte :
          - list[Lock]   → vérification par .conflicts()
          - list[str]    → toujours True (pas de lock réel)
          - list vide    → toujours True
        """
        if not locks:
            return True

        for new_lock in locks:
            if hasattr(new_lock, "conflicts"):
                for active_lock in self.locks:
                    if new_lock.conflicts(active_lock):
                        return False
        return True

    def acquire_locks(self, locks) -> None:
        """Enregistre des locks comme actifs."""
        for lock in locks:
            if hasattr(lock, "conflicts"):
                self.locks.append(lock)

    def release_locks(self, locks) -> None:
        """Libère des locks actifs."""
        for lock in locks:
            try:
                self.locks.remove(lock)
            except ValueError:
                pass

    # ═════════════════════════════════════════════════════════════════
    # RUNNING (avec gestion des locks)
    # ═════════════════════════════════════════════════════════════════

    def add_running(self, task) -> None:
        """Enregistre une task en cours et acquiert ses locks."""
        locks = getattr(task, "locks", [])
        self.start(task)
        self.acquire_locks(locks)

    def remove_running(self, task_id: str) -> None:
        """Retire une task du running et libère ses locks."""
        entry = self.running.pop(task_id, None)
        if entry:
            task = entry["task"]
            locks = getattr(task, "locks", [])
            self.release_locks(locks)

    # ═════════════════════════════════════════════════════════════════
    # WAITING (tasks en attente de ressources)
    # ═════════════════════════════════════════════════════════════════

    def add_waiting(self, task) -> None:
        self.waiting[task.id] = task

    def get_waiting(self) -> list:
        return list(self.waiting.values())

    def pop_waiting(self, task_id: str):
        return self.waiting.pop(task_id, None)

    def remove_waiting(self, task) -> None:
        self.waiting.pop(task.id, None)

    # ═════════════════════════════════════════════════════════════════
    # INTROSPECTION
    # ═════════════════════════════════════════════════════════════════

    @property
    def running_count(self) -> int:
        return len(self.running)

    @property
    def completed_count(self) -> int:
        return len(self.completed)

    @property
    def failed_count(self) -> int:
        return len(self.failed)

    @property
    def waiting_count(self) -> int:
        return len(self.waiting)

    def summary(self) -> str:
        return (
            f"running={self.running_count} "
            f"completed={self.completed_count} "
            f"failed={self.failed_count} "
            f"waiting={self.waiting_count} "
            f"locks={len(self.locks)}"
        )
