"""
Module fournissant des métriques sur les tâches du scheduler.
Récupère les données du RuntimeState global.
"""

import time
import threading
from typing import List, Dict, Any, Optional
from datetime import datetime

# Import du runtime
from .model.runtime import RuntimeState, get_global_runtime

# Registre pour les durées mesurées par le décorateur timed_task
_perf_lock = threading.Lock()
_performance_registry: Dict[str, List[float]] = {}

def record_task_duration(task_id: str, duration: float) -> None:
    """
    Enregistre la durée d'exécution d'une tâche pour les statistiques.
    Appelé par le décorateur timed_task.
    """
    with _perf_lock:
        if task_id not in _performance_registry:
            _performance_registry[task_id] = []
        _performance_registry[task_id].append(duration)

def get_task_metrics() -> List[Dict[str, Any]]:
    """
    Retourne une liste de dictionnaires représentant les tâches en cours/terminées.
    Les données sont extraites du RuntimeState global.
    """
    runtime: RuntimeState = get_global_runtime()
    tasks = []

    # Temps actuel pour les tâches en attente
    now = time.time()

    # Tâches en cours d'exécution
    for task_id, info in runtime.running.items():
        task = info.get("task")
        started = info.get("started_at", 0)
        duration = now - started if started else 0.0
        resource = ""
        if task is not None and hasattr(task, "locks"):
            locks = task.locks
            if locks and len(locks) > 0:
                # Prendre le premier lock et extraire sa ressource (si applicable)
                lock = locks[0]
                resource = str(lock)
        tasks.append({
            "id": task_id,
            "state": "En cours",
            "start_time": started,
            "duration": duration,
            "resource": resource,
        })

    # Tâches terminées avec succès
    for task_id, info in runtime.completed.items():
        task = info.get("task")
        duration = info.get("duration", 0.0)
        resource = ""
        if task is not None and hasattr(task, "locks"):
            locks = task.locks
            if locks and len(locks) > 0:
                resource = str(locks[0])
        tasks.append({
            "id": task_id,
            "state": "Terminé",
            "start_time": info.get("started_at", 0),
            "duration": duration,
            "resource": resource,
        })

    # Tâches échouées
    for task_id, info in runtime.failed.items():
        task = info.get("task")
        duration = info.get("duration", 0.0)
        resource = ""
        if task is not None and hasattr(task, "locks"):
            locks = task.locks
            if locks and len(locks) > 0:
                resource = str(locks[0])
        tasks.append({
            "id": task_id,
            "state": "Échec",
            "start_time": info.get("started_at", 0),
            "duration": duration,
            "resource": resource,
        })

    # Tâches en attente (waiting)
    for task_id, task in runtime.waiting.items():
        resource = ""
        if task is not None and hasattr(task, "locks"):
            locks = task.locks
            if locks and len(locks) > 0:
                resource = str(locks[0])
        tasks.append({
            "id": task_id,
            "state": "En attente",
            "start_time": now,
            "duration": 0.0,
            "resource": resource,
        })

    return tasks


def get_performance_stats() -> Dict[str, float]:
    """
    Retourne des statistiques de performance du scheduler basées sur le registre de durées.
    """
    with _perf_lock:
        all_durations = []
        for lst in _performance_registry.values():
            all_durations.extend(lst)
        if not all_durations:
            avg = 0.0
        else:
            avg = sum(all_durations) / len(all_durations)
        total_tasks = len(all_durations)
        # Estimation de tâches par minute
        uptime = get_global_runtime().uptime
        tasks_per_minute = (total_tasks / uptime) * 60 if uptime > 0 else 0.0
        queue_len = get_global_runtime().waiting_count
        return {
            "avg_task_duration": avg,
            "tasks_per_minute": tasks_per_minute,
            "queue_length": queue_len,
            "uptime_hours": uptime / 3600.0,
        }


def get_log_severity_stats() -> Dict[str, int]:
    """
    Retourne le nombre d'entrées de log par niveau de sévérité.
    """
    from .intentlog.log import intent_log
    return intent_log.severity_counts()


def get_log_export_stats() -> Dict[str, Any]:
    """
    Retourne des statistiques sur les logs compressés.
    """
    from .intentlog.log import intent_log
    total = intent_log.total_count
    failed = intent_log.failure_count
    return {
        "total_entries": total,
        "failed_entries": failed,
        "success_ratio": (total - failed) / total if total > 0 else 1.0,
    }
