"""
fsdeploy.scheduler.model.runtime
=================================
Source unique de vérité pour l'état du scheduler.

Thread-safe : toutes les mutations sont protégées par un Lock.
Les callbacks du ThreadPoolExecutor (release_locks, success, fail)
s'exécutent dans un thread du pool tandis que le scheduler tourne
dans le thread principal.

Combine :
  - cycle de vie des tasks   (start / success / fail)
  - gestion des locks         (conflits, parallélisme)
  - file d'attente waiting    (tasks en attente de ressources)

Utilisé par :
  - Executor  → start(), success(), fail(), release_locks()
  - Scheduler → can_run(), acquire_locks(), add_waiting()
  - Runtime   → self.state = RuntimeState()
"""

import time
import threading
from typing import Any, Optional


class RuntimeState:

    def __init__(self):
        # ── Thread safety ─────────────────────────────────────────────
        self._lock = threading.Lock()
        self._start_time = time.monotonic()

        # ── Parallélisme ────────────────────────────────────────────────
        import os
        max_parallel_env = os.environ.get("FSDEPLOY_MAX_PARALLEL")
        if max_parallel_env is not None and max_parallel_env.isdigit():
            self.max_parallel = int(max_parallel_env)
        else:
            self.max_parallel = 5   # nombre maximum de tâches à exécuter en parallèle

        # ── Retry ───────────────────────────────────────────────────────
        self.max_retries = 3                     # nombre maximal de tentatives par défaut
        retry_env = os.environ.get("FSDEPLOY_MAX_RETRIES")
        if retry_env is not None and retry_env.isdigit():
            self.max_retries = int(retry_env)
        else:
            self.max_retries = 3

        self.retry_base_delay = 1.0              # délai de base en secondes
        base_delay_env = os.environ.get("FSDEPLOY_RETRY_BASE_DELAY")
        if base_delay_env is not None:
            try:
                self.retry_base_delay = float(base_delay_env)
            except ValueError:
                pass

        self.retry_backoff_factor = 2.0          # facteur exponentiel
        backoff_env = os.environ.get("FSDEPLOY_RETRY_BACKOFF_FACTOR")
        if backoff_env is not None:
            try:
                self.retry_backoff_factor = float(backoff_env)
            except ValueError:
                pass

        self.retry_max_delay = 3600.0            # délai maximum (1 heure)
        max_delay_env = os.environ.get("FSDEPLOY_RETRY_MAX_DELAY")
        if max_delay_env is not None:
            try:
                self.retry_max_delay = float(max_delay_env)
            except ValueError:
                pass

        self.retry_counts: dict[str, int] = {}   # id tâche → nombre d'échecs
        self._retry_timestamps: dict[str, float] = {}  # id → timestamp dernier échec
        self._retry_delays: dict[str, float] = {}      # id → délai calculé pour la prochaine tentative

        # ── Cycle de vie ──────────────────────────────────────────────
        self.running: dict[str, dict] = {}       # id → {task, status, started_at}
        self.completed: dict[str, dict] = {}     # id → {task, result, status, duration}
        self.failed: dict[str, dict] = {}        # id → {task, error, status, duration}

        # ── Waiting ───────────────────────────────────────────────────
        self.waiting: dict[str, Any] = {}        # id → task (O(1) access)
        self.waiting_ts: dict[str, float] = {}   # id → timestamp when added

        # ── Locks actifs ──────────────────────────────────────────────
        self.locks: list = []                    # list[Lock]

        # ── Métriques de performance ──────────────────────────────────
        self._completion_times: list[float] = []   # timestamps des tâches terminées
        self._max_completion_times = 1000

        # ── Adaptation de parallélisme ────────────────────────────────
        self._throughput_history: list[float] = []           # débit mesuré (tâches/s)
        self._max_parallel_history: list[int] = []           # valeurs de max_parallel
        self._adaptation_interval = 50                       # nombre de tâches terminées entre deux ajustements
        self._adaptation_counter = 0

    # ═════════════════════════════════════════════════════════════════
    # CYCLE DE VIE (appelé par Executor — potentiellement depuis un thread pool)
    # ═════════════════════════════════════════════════════════════════

    def start(self, task) -> None:
        """Marque une task comme en cours d'exécution."""
        with self._lock:
            self.running[task.id] = {
                "task": task,
                "status": "running",
                "started_at": time.monotonic(),
            }

    def success(self, task, result=None) -> None:
        """Marque une task comme terminée avec succès."""
        with self._lock:
            # Réinitialiser le compteur d'échecs et les métadonnées de réessai
            self.retry_counts.pop(task.id, None)
            self._retry_timestamps.pop(task.id, None)
            self._retry_delays.pop(task.id, None)
            entry = self.running.pop(task.id, None)
            started = entry["started_at"] if entry else 0
            self.completed[task.id] = {
                "task": task,
                "result": result,
                "status": "success",
                "duration": time.monotonic() - started,
            }
            self._record_completion(time.monotonic())

    def fail(self, task, error: Exception | str = None) -> None:
        """Marque une task comme échouée."""
        with self._lock:
            # Incrémenter le compteur d'échecs
            self.retry_counts[task.id] = self.retry_counts.get(task.id, 0) + 1
            # Calcul du délai avant réessai (backoff exponentiel)
            now = time.monotonic()
            self._retry_timestamps[task.id] = now
            cnt = self.retry_counts[task.id]
            delay = self.retry_base_delay * (self.retry_backoff_factor ** (cnt - 1))
            delay = min(delay, self.retry_max_delay)
            self._retry_delays[task.id] = delay
            entry = self.running.pop(task.id, None)
            started = entry["started_at"] if entry else 0

            # Libérer les locks de la tâche
            locks = getattr(task, "locks", [])
            self._release_locks_held(locks)

            if self.can_retry(task.id):
                # La tâche peut être réessayée plus tard
                # Ne pas l'ajouter à failed, mais la replacer dans waiting
                # Le scheduler devra vérifier is_ready_for_retry avant de la sélectionner
                self.waiting[task.id] = task
                self.waiting_ts[task.id] = now
            else:
                # Plus de tentatives
                self.failed[task.id] = {
                    "task": task,
                    "error": error,
                    "status": "failed",
                    "duration": time.monotonic() - started,
                }
                self._record_completion(now)

    def is_running(self, task) -> bool:
        with self._lock:
            return task.id in self.running

    # ═════════════════════════════════════════════════════════════════
    # LOCKS ET PARALLÉLISME
    # ═════════════════════════════════════════════════════════════════

    def can_run(self, locks, lock_held=False) -> bool:
        """
        Vérifie qu'aucun lock demandé ne conflicte avec un lock actif.
        Si lock_held est True, le verrou du runtime est déjà acquis.

        Accepte :
          - list[Lock]   → vérification par .conflicts()
          - list[str]    → toujours True (pas de lock réel)
          - list vide    → toujours True
        """
        if not locks:
            return True

        if not lock_held:
            with self._lock:
                return self._can_run_held(locks)
        else:
            return self._can_run_held(locks)

    def _can_run_held(self, locks):
        """Vérifie les conflits avec les locks actifs, en supposant que le verrou est déjà tenu."""
        for new_lock in locks:
            if hasattr(new_lock, "conflicts"):
                for active_lock in self.locks:
                    if hasattr(active_lock, "conflicts") and new_lock.conflicts(active_lock):
                        return False
        return True

    def _release_locks_held(self, locks):
        """Libère des locks actifs, en supposant que le verrou est déjà acquis."""
        for lock in locks:
            try:
                self.locks.remove(lock)
            except ValueError:
                pass

    def _locks_conflict(self, locks_a, locks_b) -> bool:
        """
        Vérifie si une lock de locks_a est en conflit avec une lock de locks_b.
        """
        for lock_a in locks_a:
            if not hasattr(lock_a, "conflicts"):
                continue
            for lock_b in locks_b:
                if not hasattr(lock_b, "conflicts"):
                    continue
                if lock_a.conflicts(lock_b):
                    return True
        return False

    def acquire_locks(self, locks) -> None:
        """Enregistre des locks comme actifs."""
        with self._lock:
            for lock in locks:
                if hasattr(lock, "conflicts"):
                    self.locks.append(lock)

    def release_locks(self, locks) -> None:
        """Libère des locks actifs."""
        with self._lock:
            self._release_locks_held(locks)

    # ═════════════════════════════════════════════════════════════════
    # RUNNING (sans double acquisition — le Scheduler acquiert,
    #          l'Executor libère via release_locks)
    # ═════════════════════════════════════════════════════════════════

    def add_running(self, task) -> None:
        """
        Enregistre une task en cours et acquiert ses locks.

        ATTENTION : utilisé uniquement pour la compatibilité.
        Le flow normal est : Scheduler.acquire_locks() → Executor.execute()
        → callback release_locks().
        """
        locks = getattr(task, "locks", [])
        self.start(task)
        self.acquire_locks(locks)

    def remove_running(self, task_id: str) -> None:
        """Retire une task du running et libère ses locks."""
        with self._lock:
            entry = self.running.pop(task_id, None)
            if entry:
                task = entry["task"]
                locks = getattr(task, "locks", [])
                for lock in locks:
                    try:
                        self.locks.remove(lock)
                    except ValueError:
                        pass

    # ═════════════════════════════════════════════════════════════════
    # WAITING (tasks en attente de ressources)
    # ═════════════════════════════════════════════════════════════════

    def add_waiting(self, task) -> None:
        with self._lock:
            self.waiting[task.id] = task
            self.waiting_ts[task.id] = time.monotonic()

    def get_waiting(self) -> list:
        with self._lock:
            return list(self.waiting.values())

    def pop_waiting(self, task_id: str):
        with self._lock:
            self.waiting_ts.pop(task_id, None)
            return self.waiting.pop(task_id, None)

    def remove_waiting(self, task) -> None:
        with self._lock:
            self.waiting.pop(task.id, None)
            self.waiting_ts.pop(task.id, None)

    def select_runnable_tasks(self, max_tasks: int = None) -> list:
        """
        Sélectionne jusqu'à max_tasks tâches en attente qui peuvent s'exécuter
        immédiatement sans conflits de locks entre elles ni avec les locks actifs.
        Si max_tasks n'est pas spécifié, utilise self.max_parallel.
        """
        with self._lock:
            if max_tasks is None:
                max_tasks = self.max_parallel
            waiting = list(self.waiting.values())
            now = time.monotonic()
            # Calcul du score de priorité : temps d'attente / (nombre de locks + 1)
            scored = []
            for task in waiting:
                locks = getattr(task, "locks", [])
                lock_cnt = len(locks)
                ts = self.waiting_ts.get(task.id, now)
                wait_time = now - ts
                # Éviter division par zéro
                score = wait_time / (lock_cnt + 1.0)
                scored.append((score, task))
            # Trier par score décroissant (priorité élevée d'abord)
            scored.sort(key=lambda x: -x[0])
            waiting = [task for _, task in scored]
            selected = []
            selected_locks = []
            for task in waiting:
                if len(selected) >= max_tasks:
                    break
                # Vérifier si la tâche est prête pour un réessai (délai écoulé)
                if not self._is_ready_for_retry_held(task.id):
                    continue
                locks = getattr(task, "locks", [])
                # Vérifier conflit avec locks actifs
                if not self.can_run(locks, lock_held=True):
                    continue
                # Vérifier conflit avec locks des tâches déjà sélectionnées
                if self._locks_conflict(locks, selected_locks):
                    continue
                selected.append(task)
                selected_locks.extend(locks)
            return selected

    def acquire_tasks(self, max_tasks: int = None) -> list:
        """
        Sélectionne jusqu'à max_tasks tâches en attente, acquiert leurs locks
        et les retire de la file waiting, de manière atomique.
        Retourne la liste des tâches acquises.
        """
        with self._lock:
            if max_tasks is None:
                max_tasks = self.max_parallel
            waiting = list(self.waiting.values())
            now = time.monotonic()
            # Calcul du score de priorité : temps d'attente / (nombre de locks + 1)
            scored = []
            for task in waiting:
                locks = getattr(task, "locks", [])
                lock_cnt = len(locks)
                ts = self.waiting_ts.get(task.id, now)
                wait_time = now - ts
                # Éviter division par zéro
                score = wait_time / (lock_cnt + 1.0)
                scored.append((score, task))
            # Trier par score décroissant (priorité élevée d'abord)
            scored.sort(key=lambda x: -x[0])
            waiting = [task for _, task in scored]
            selected = []
            selected_locks = []
            for task in waiting:
                if len(selected) >= max_tasks:
                    break
                # Vérifier si la tâche est prête pour un réessai (délai écoulé)
                if not self._is_ready_for_retry_held(task.id):
                    continue
                locks = getattr(task, "locks", [])
                # Vérifier conflit avec locks actifs
                if not self._can_run_held(locks):
                    continue
                # Vérifier conflit avec locks des tâches déjà sélectionnées
                if self._locks_conflict(locks, selected_locks):
                    continue
                selected.append(task)
                selected_locks.extend(locks)
            # Maintenant, acquérir les locks et retirer de waiting
            for task in selected:
                self.locks.extend(getattr(task, "locks", []))
                self.waiting.pop(task.id, None)
                self.waiting_ts.pop(task.id, None)
            return selected

    def _compute_conflict_stats(self, waiting: list) -> dict:
        """
        Calcule des statistiques de conflits entre les tâches en attente.
        Retourne un dict avec :
          - conflict_degree_avg : nombre moyen de conflits par tâche
          - conflict_degree_max : maximum de conflits pour une tâche
          - conflict_degree_min : minimum de conflits pour une tâche
          - conflict_pairs       : nombre total de paires en conflit
        """
        if not waiting:
            return {
                "conflict_degree_avg": 0.0,
                "conflict_degree_max": 0,
                "conflict_degree_min": 0,
                "conflict_pairs": 0,
            }
        conflicts_per_task = []
        for i, task_i in enumerate(waiting):
            locks_i = getattr(task_i, "locks", [])
            cnt = 0
            for j, task_j in enumerate(waiting):
                if i == j:
                    continue
                locks_j = getattr(task_j, "locks", [])
                if self._locks_conflict(locks_i, locks_j):
                    cnt += 1
            conflicts_per_task.append(cnt)
        total_pairs = sum(conflicts_per_task) // 2  # chaque conflit compté deux fois
        return {
            "conflict_degree_avg": sum(conflicts_per_task) / len(conflicts_per_task),
            "conflict_degree_max": max(conflicts_per_task) if conflicts_per_task else 0,
            "conflict_degree_min": min(conflicts_per_task) if conflicts_per_task else 0,
            "conflict_pairs": total_pairs,
        }

    def parallelism_report(self) -> dict:
        """
        Retourne des statistiques sur le potentiel de parallélisme.
        """
        with self._lock:
            waiting = list(self.waiting.values())
            total = len(waiting)
            lock_counts = [len(getattr(t, "locks", [])) for t in waiting]
            avg_locks = sum(lock_counts) / total if total else 0
            active_locks = list(self.locks)
            max_possible = 0
            selected_locks = []
            # Trier par nombre de locks croissant pour l'estimation
            sorted_tasks = sorted(waiting, key=lambda t: len(getattr(t, "locks", [])))
            for task in sorted_tasks:
                locks = getattr(task, "locks", [])
                if not self._locks_conflict(locks, active_locks) and not self._locks_conflict(locks, selected_locks):
                    max_possible += 1
                    selected_locks.extend(locks)
            conflict_stats = self._compute_conflict_stats(waiting)
            return {
                "waiting_tasks": total,
                "average_locks_per_task": avg_locks,
                "estimated_parallel_slots": max_possible,
                "current_max_parallel": self.max_parallel,
                "active_locks": len(self.locks),
                "running_tasks": len(self.running),
                "conflict_degree_avg": conflict_stats["conflict_degree_avg"],
                "conflict_degree_max": conflict_stats["conflict_degree_max"],
                "conflict_degree_min": conflict_stats["conflict_degree_min"],
                "conflict_pairs": conflict_stats["conflict_pairs"],
            }

    def set_max_parallel(self, n: int) -> None:
        """Définit le nombre maximum de tâches à exécuter en parallèle."""
        with self._lock:
            self.max_parallel = max(1, n)

    # ═════════════════════════════════════════════════════════════════
    # INTROSPECTION
    # ═════════════════════════════════════════════════════════════════

    @property
    def running_count(self) -> int:
        with self._lock:
            return len(self.running)

    @property
    def completed_count(self) -> int:
        with self._lock:
            return len(self.completed)

    @property
    def failed_count(self) -> int:
        with self._lock:
            return len(self.failed)

    @property
    def waiting_count(self) -> int:
        with self._lock:
            return len(self.waiting)

    @property
    def lock_count(self) -> int:
        with self._lock:
            return len(self.locks)

    @property
    def uptime(self) -> float:
        """Retourne le temps écoulé depuis la création en secondes."""
        return time.monotonic() - self._start_time

    def validate_locks(self) -> list[str]:
        """
        Vérifie la cohérence interne des locks.
        Retourne une liste de messages d'erreur (vide si tout est cohérent).
        """
        import logging
        logger = logging.getLogger(__name__)
        errors = []
        with self._lock:
            # Pour chaque tâche en cours, récupérer ses locks et s'assurer qu'ils sont dans self.locks
            for task_id, info in self.running.items():
                task = info.get("task")
                if task is None:
                    errors.append(f"Tâche {task_id} en cours n'a pas d'objet task.")
                    continue
                locks = getattr(task, "locks", [])
                for lock in locks:
                    if hasattr(lock, "conflicts"):
                        if lock not in self.locks:
                            errors.append(f"Lock {lock} de la tâche {task_id} manquant dans self.locks")
            # Vérifier que chaque lock dans self.locks est bien détenu par une tâche en cours
            for lock in self.locks:
                found = False
                for task_id, info in self.running.items():
                    task = info.get("task")
                    if task is None:
                        continue
                    locks = getattr(task, "locks", [])
                    if lock in locks:
                        found = True
                        break
                if not found:
                    errors.append(f"Lock {lock} orphelin (aucune tâche en cours ne le détient)")
        if errors:
            logger.warning("Incohérences de locks détectées : %s", errors)
        return errors

    # ═════════════════════════════════════════════════════════════════
    # RETRY SUPPORT
    # ═════════════════════════════════════════════════════════════════

    def increment_retry(self, task_id: str) -> int:
        """Incrémente le compteur d'échec pour la tâche et retourne le nouveau compte."""
        with self._lock:
            self.retry_counts[task_id] = self.retry_counts.get(task_id, 0) + 1
            return self.retry_counts[task_id]

    def get_retry_count(self, task_id: str) -> int:
        """Retourne le nombre d'échecs enregistrés pour la tâche."""
        with self._lock:
            return self.retry_counts.get(task_id, 0)

    def clear_retry(self, task_id: str) -> None:
        """Réinitialise le compteur d'échecs pour la tâche."""
        with self._lock:
            self.retry_counts.pop(task_id, None)
            self._retry_timestamps.pop(task_id, None)
            self._retry_delays.pop(task_id, None)

    def can_retry(self, task_id: str, max_retries: int | None = None) -> bool:
        """
        Indique si une tâche peut être réessayée selon le nombre maximal autorisé.
        Si max_retries est None, utilise self.max_retries.
        """
        if max_retries is None:
            max_retries = self.max_retries
        with self._lock:
            return self.retry_counts.get(task_id, 0) < max_retries

    def set_max_retries(self, n: int) -> None:
        """Définit le nombre maximal de tentatives par défaut."""
        with self._lock:
            self.max_retries = max(0, n)

    def retry_info(self, task_id: str) -> dict:
        """Retourne les informations de réessai pour une tâche."""
        with self._lock:
            cnt = self.retry_counts.get(task_id, 0)
            last = self._retry_timestamps.get(task_id)
            delay = self._retry_delays.get(task_id, 0.0)
            now = time.monotonic()
            ready = (last is not None) and (now >= last + delay)
            return {
                "count": cnt,
                "last_failure": last,
                "next_retry_delay": delay,
                "ready": ready,
                "max_retries": self.max_retries,
            }

    def is_ready_for_retry(self, task_id: str) -> bool:
        """Indique si une tâche peut être réessayée maintenant (délai écoulé)."""
        with self._lock:
            last = self._retry_timestamps.get(task_id)
            if last is None:
                return True  # aucune précédente tentative
            delay = self._retry_delays.get(task_id, 0.0)
            return time.monotonic() >= last + delay

    def _is_ready_for_retry_held(self, task_id: str) -> bool:
        """Version de is_ready_for_retry à appeler lorsque le lock est déjà acquis."""
        last = self._retry_timestamps.get(task_id)
        if last is None:
            return True  # aucune précédente tentative
        delay = self._retry_delays.get(task_id, 0.0)
        return time.monotonic() >= last + delay

    def _record_completion(self, timestamp: float) -> None:
        """Enregistre un timestamp de complétion pour le calcul du débit."""
        self._completion_times.append(timestamp)
        # Garder une taille raisonnable
        if len(self._completion_times) > self._max_completion_times:
            # Supprimer le plus ancien (première entrée)
            self._completion_times.pop(0)

    def throughput(self, window_seconds: float = 60.0) -> float:
        """
        Retourne le nombre de tâches terminées (succès + échec) par seconde
        sur la fenêtre temporelle donnée.
        """
        with self._lock:
            now = time.monotonic()
            cutoff = now - window_seconds
            # Les timestamps sont triés par ordre croissant
            # Utiliser la recherche binaire pour efficacité
            import bisect
            start_idx = bisect.bisect_left(self._completion_times, cutoff)
            count = len(self._completion_times) - start_idx
            return count / window_seconds if window_seconds > 0 else 0.0

    def waiting_retry_report(self) -> list[dict]:
        """Retourne un rapport détaillé des tâches en attente avec leurs infos de réessai."""
        with self._lock:
            report = []
            for task_id, task in self.waiting.items():
                info = self.retry_info(task_id)
                report.append({
                    "task_id": task_id,
                    "class": type(task).__name__,
                    "retry_count": info["count"],
                    "last_failure": info["last_failure"],
                    "next_retry_delay": info["next_retry_delay"],
                    "ready_for_retry": info["ready"],
                    "max_retries": info["max_retries"],
                    "waiting_since": self.waiting_ts.get(task_id),
                })
            return report

    def auto_tune_parallelism(self, factor: float = 0.8) -> None:
        """
        Ajuste automatiquement max_parallel en fonction des slots parallèles estimés.
        factor : proportion des slots estimés à utiliser (par défaut 0.8).
        """
        report = self.parallelism_report()
        estimated = report["estimated_parallel_slots"]
        if estimated > self.max_parallel:
            # on peut augmenter
            new = int(self.max_parallel * 1.5)
        else:
            # réduire si trop de slots inutilisés
            new = max(1, int(estimated * factor))
        self.set_max_parallel(new)

    def recommend_parallel(self, aggressive: bool = False) -> int:
        """
        Recommande un nombre de tâches à exécuter en parallèle,
        basé sur les statistiques de conflits et la charge actuelle.
        Si aggressive est True, tente d'utiliser davantage de slots.
        """
        with self._lock:
            waiting = list(self.waiting.values())
            running = len(self.running)
            if not waiting:
                return max(1, running)

            # Compter combien de tâches peuvent réellement s'exécuter ensemble
            # en utilisant l'algorithme glouton de select_runnable_tasks
            test_max = min(len(waiting), self.max_parallel * 2 if aggressive else self.max_parallel)
            selected = []
            selected_locks = []
            # Trier par nombre de locks croissant (priorité aux tâches légères)
            sorted_tasks = sorted(waiting, key=lambda t: len(getattr(t, "locks", [])))
            for task in sorted_tasks:
                if len(selected) >= test_max:
                    break
                locks = getattr(task, "locks", [])
                if not self._can_run_held(locks):
                    continue
                if self._locks_conflict(locks, selected_locks):
                    continue
                selected.append(task)
                selected_locks.extend(locks)
            # On prend le minimum entre le nombre sélectionné et max_parallel,
            # mais on garantit au moins 1
            recommended = max(1, min(len(selected), self.max_parallel))
            # Si aggressive et qu'on a des slots libres, on peut suggérer un peu plus
            if aggressive and len(selected) > self.max_parallel:
                recommended = min(len(selected), self.max_parallel + 1)
            return recommended

    def tune_based_on_load(self, target_ratio: float = 2.0) -> None:
        """
        Ajuste max_parallel pour essayer de maintenir waiting_count <= target_ratio * running_count.
        Si waiting_count > target_ratio * running_count, on augmente max_parallel de 1.
        Sinon, on le diminue de 1 (minimum 1).
        """
        with self._lock:
            waiting = len(self.waiting)
            running = len(self.running)
            if waiting > target_ratio * running:
                # augmenter
                self.max_parallel = min(self.max_parallel + 1, 50)  # limite haute arbitraire
            else:
                # diminuer
                self.max_parallel = max(self.max_parallel - 1, 1)

    def load_factors(self) -> dict:
        """
        Retourne des indicateurs de charge pour le réglage du parallélisme.
        """
        with self._lock:
            waiting = len(self.waiting)
            running = len(self.running)
            completed = len(self.completed)
            failed = len(self.failed)
            throughput = self.throughput(60.0)
            return {
                "waiting": waiting,
                "running": running,
                "completed": completed,
                "failed": failed,
                "throughput_60s": throughput,
                "waiting_ratio": waiting / (running + 1e-9),
                "locks_count": len(self.locks),
                "max_parallel": self.max_parallel,
            }

    def summary(self) -> str:
        with self._lock:
            return (
                f"running={len(self.running)} "
                f"completed={len(self.completed)} "
                f"failed={len(self.failed)} "
                f"waiting={len(self.waiting)} "
                f"locks={len(self.locks)}"
            )

    def adaptive_parallelism_step(self) -> dict:
        """
        Effectue un pas d'adaptation du parallélisme basé sur l'historique récent.
        Retourne un dict avec les décisions prises.
        """
        with self._lock:
            self._adaptation_counter += 1
            if self._adaptation_counter < self._adaptation_interval:
                return {"action": "none", "reason": "interval_not_reached"}
            self._adaptation_counter = 0

            # Récupérer les indicateurs actuels
            load = self.load_factors()
            report = self.parallelism_report()

            # Calculer le débit sur la dernière minute
            recent_throughput = self.throughput(60.0)
            # Garder un historique
            self._throughput_history.append(recent_throughput)
            self._max_parallel_history.append(self.max_parallel)
            # Limiter la taille de l'historique
            if len(self._throughput_history) > 20:
                self._throughput_history.pop(0)
                self._max_parallel_history.pop(0)

            # Décision simple : si le débit a baissé et que max_parallel est élevé, diminuer
            # Si le débit est stable et qu'il y a beaucoup de tâches en attente, augmenter
            action = "none"
            reason = ""
            if len(self._throughput_history) >= 3:
                last_three = self._throughput_history[-3:]
                avg_throughput = sum(last_three) / 3
                if recent_throughput < avg_throughput * 0.9 and self.max_parallel > 1:
                    # baisser
                    self.max_parallel = max(1, self.max_parallel - 1)
                    action = "decrease"
                    reason = "throughput_declining"
                elif load["waiting_ratio"] > 2.0 and recent_throughput >= avg_throughput:
                    # augmenter si beaucoup d'attente et débit stable
                    self.max_parallel = min(self.max_parallel + 1, 50)
                    action = "increase"
                    reason = "high_waiting_ratio"
            return {
                "action": action,
                "reason": reason,
                "throughput": recent_throughput,
                "waiting_ratio": load["waiting_ratio"],
                "new_max_parallel": self.max_parallel,
            }

# ═════════════════════════════════════════════════════════════════
# INSTANCE GLOBALE (singleton)
# ═════════════════════════════════════════════════════════════════

_global_runtime: Optional[RuntimeState] = None


def get_global_runtime() -> RuntimeState:
    """Retourne l'instance globale du RuntimeState, en en créant une si nécessaire."""
    global _global_runtime
    if _global_runtime is None:
        _global_runtime = RuntimeState()
    return _global_runtime
