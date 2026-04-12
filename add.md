# add.md — Action 3.3 : Scheduler.state_snapshot() pour GraphViewScreen

**Date** : 2026-04-12

---

## Problème

`bridge.get_scheduler_state()` appelle `scheduler.state_snapshot()` mais cette méthode n'existe pas dans `Scheduler`. Le bridge retourne des données aléatoires de démo → GraphViewScreen n'affiche jamais de vraies données.

---

## Correction

### `lib/scheduler/core/scheduler.py` — ajouter `state_snapshot()`

```python
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
```

---

## Fichier Aider

```
fsdeploy/lib/scheduler/core/scheduler.py
```

---

## Après

3.3 terminé. Prochaine : **3.4** (FileHandler pour logs persistants).
