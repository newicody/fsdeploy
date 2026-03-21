"""
fsdeploy.ui.screens.graph
===========================
GraphViewScreen — Visualisation temps réel du scheduler.

Widgets :
  - PipelineStages : affiche EventQueue → IntentQueue → TaskGraph → Done
  - TaskDetail : détails de la tâche active
  - TaskHistory : historique scrollable des tâches

Fonctionnalités :
  - Animation 10 FPS
  - Auto-centrage sur tâche active
  - Pause/Resume
  - Navigation temporelle
"""

import os
import time
from typing import Any, Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual.screen import Screen
from textual.widgets import (
    Button, DataTable, Label, ProgressBar, Rule, Static,
)
from textual.timer import Timer
from textual.reactive import reactive


IS_FB = os.environ.get("TERM") == "linux"

# Icônes avec fallback ASCII
ICONS = {
    "pending": "⏳" if not IS_FB else "[.]",
    "running": "🔄" if not IS_FB else "[>]",
    "completed": "✅" if not IS_FB else "[+]",
    "failed": "❌" if not IS_FB else "[X]",
    "paused": "⏸️" if not IS_FB else "[=]",
    "arrow": "→" if not IS_FB else "->",
}


# ─── Widgets ──────────────────────────────────────────────────────────────────

class PipelineStages(Static):
    """
    Affiche les stages du pipeline :
    [EventQueue] → [IntentQueue] → [TaskGraph] → [Done]
    """

    event_count: reactive[int] = reactive(0)
    intent_count: reactive[int] = reactive(0)
    task_count: reactive[int] = reactive(0)
    completed_count: reactive[int] = reactive(0)

    def render(self) -> str:
        arrow = ICONS["arrow"]
        pending = ICONS["pending"]
        running = ICONS["running"]
        done = ICONS["completed"]

        return (
            f"  [{pending} EventQueue: {self.event_count}] {arrow} "
            f"[{pending} IntentQueue: {self.intent_count}] {arrow} "
            f"[{running} TaskGraph: {self.task_count}] {arrow} "
            f"[{done} Done: {self.completed_count}]"
        )

    def update_counts(
        self,
        events: int = 0,
        intents: int = 0,
        tasks: int = 0,
        completed: int = 0,
    ) -> None:
        self.event_count = events
        self.intent_count = intents
        self.task_count = tasks
        self.completed_count = completed


class TaskDetail(Static):
    """Affiche les détails de la tâche active."""

    DEFAULT_CSS = """
    TaskDetail {
        height: auto;
        min-height: 5;
        padding: 1 2;
        border: solid $accent;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._task_data: dict = {}

    def update_task(self, task_data: dict) -> None:
        self._task_data = task_data
        self.refresh()

    def render(self) -> str:
        if not self._task_data:
            return "  Aucune tâche active"

        task_id = self._task_data.get("id", "?")
        task_type = self._task_data.get("type", "?")
        status = self._task_data.get("status", "?")
        progress = self._task_data.get("progress", 0)
        elapsed = self._task_data.get("elapsed", 0)
        params = self._task_data.get("params", {})

        icon = ICONS.get(status, ICONS["running"])
        bar_width = 30
        filled = int(progress / 100 * bar_width)
        bar = "█" * filled + "░" * (bar_width - filled)

        lines = [
            f"  {icon} {task_type} ({task_id})",
            f"  Status: {status.upper()}  |  Elapsed: {elapsed:.1f}s",
            f"  [{bar}] {progress:.0f}%",
        ]

        if params:
            param_str = ", ".join(f"{k}={v}" for k, v in list(params.items())[:3])
            lines.append(f"  Params: {param_str}")

        return "\n".join(lines)


class TaskHistory(ScrollableContainer):
    """Historique scrollable des tâches."""

    DEFAULT_CSS = """
    TaskHistory {
        height: 1fr;
        border: solid $primary;
        padding: 0 1;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._tasks: list[dict] = []

    def compose(self) -> ComposeResult:
        yield DataTable(id="history-table")

    def on_mount(self) -> None:
        table = self.query_one("#history-table", DataTable)
        table.add_columns("Status", "Task", "Duration")
        table.zebra_stripes = True

    def update_history(self, tasks: list[dict]) -> None:
        self._tasks = tasks
        table = self.query_one("#history-table", DataTable)
        table.clear()

        for task in reversed(tasks[-50:]):  # Dernières 50 tâches
            status = task.get("status", "?")
            icon = ICONS.get(status, "?")
            task_id = task.get("id", "?")
            task_type = task.get("type", "")
            duration = task.get("duration", 0)

            if task_type:
                display = f"{task_type} ({task_id})"
            else:
                display = task_id

            dur_str = f"{duration:.1f}s" if status == "completed" else status

            table.add_row(icon, display, dur_str)


# ─── Screen principal ─────────────────────────────────────────────────────────

class GraphViewScreen(Screen):
    """
    Écran de visualisation du scheduler en temps réel.
    """

    BINDINGS = [
        Binding("space", "toggle_pause", "Pause/Resume", show=True),
        Binding("r", "refresh_now", "Refresh", show=True),
        Binding("c", "clear_history", "Clear", show=True),
        Binding("escape", "app.pop_screen", "Retour", show=False),
        Binding("q", "app.pop_screen", "Quitter", show=True),
    ]

    DEFAULT_CSS = """
    GraphViewScreen {
        layout: vertical;
    }

    #graph-header {
        height: auto;
        padding: 1 2;
        text-style: bold;
        background: $primary-background;
    }

    #pipeline-container {
        height: auto;
        padding: 1 0;
        background: $surface;
    }

    #detail-container {
        height: auto;
        min-height: 7;
        margin: 0 1;
    }

    #history-container {
        height: 1fr;
        margin: 0 1 1 1;
    }

    #status-bar {
        height: 1;
        dock: bottom;
        background: $primary-background;
        padding: 0 2;
    }
    """

    paused: reactive[bool] = reactive(False)
    refresh_rate: reactive[float] = reactive(0.1)  # 10 FPS

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = "graph"
        self._timer: Optional[Timer] = None
        self._last_state: dict = {}
        self._tick_count: int = 0

    @property
    def bridge(self):
        return getattr(self.app, "bridge", None)

    @property
    def scheduler(self):
        return getattr(self.app, "scheduler", None)

    def compose(self) -> ComposeResult:
        yield Static("Pipeline Execution — Temps réel", id="graph-header")

        with Vertical(id="pipeline-container"):
            yield PipelineStages(id="pipeline")

        yield Rule()

        with Vertical(id="detail-container"):
            yield Label("Tâche active", classes="section-title")
            yield TaskDetail(id="task-detail")

        with Vertical(id="history-container"):
            yield Label("Historique", classes="section-title")
            yield TaskHistory(id="task-history")

        yield Static("", id="status-bar")

    def on_mount(self) -> None:
        """Démarre le timer de refresh."""
        self._timer = self.set_interval(self.refresh_rate, self._tick)
        self._update_status_bar()

    def on_unmount(self) -> None:
        """Arrête le timer."""
        if self._timer:
            self._timer.stop()

    # ── Tick principal ────────────────────────────────────────────────────────

    def _tick(self) -> None:
        """Appelé à chaque tick (10 FPS par défaut)."""
        if self.paused:
            return

        self._tick_count += 1

        # Récupérer l'état du scheduler
        state = self._get_scheduler_state()
        if not state:
            return

        self._last_state = state

        # Mettre à jour les widgets
        self._update_pipeline(state)
        self._update_task_detail(state)
        self._update_history(state)
        self._update_status_bar()

    def _get_scheduler_state(self) -> dict:
        """Récupère l'état du scheduler."""
        # Via bridge
        if self.bridge:
            try:
                return self.bridge.get_scheduler_state()
            except Exception:
                pass

        # Direct
        if self.scheduler:
            try:
                return self.scheduler.get_state_snapshot()
            except Exception:
                pass

        # Demo mode
        return self._generate_demo_state()

    def _generate_demo_state(self) -> dict:
        """Génère un état de démo pour les tests."""
        import random

        return {
            "event_count": random.randint(0, 5),
            "intent_count": random.randint(0, 3),
            "task_count": random.randint(1, 4),
            "completed_count": self._tick_count // 10,
            "active_task": {
                "id": f"task_{self._tick_count % 100}",
                "type": random.choice([
                    "DatasetProbeTask",
                    "PoolImportTask",
                    "KernelSwitchTask",
                    "SnapshotCreateTask",
                ]),
                "status": "running",
                "progress": (self._tick_count * 3) % 100,
                "elapsed": (self._tick_count % 50) * 0.1,
                "params": {"pool": "boot_pool"},
            },
            "recent_tasks": [
                {
                    "id": f"task_{i}",
                    "type": "DatasetProbeTask",
                    "status": "completed" if i < self._tick_count // 15 else "pending",
                    "duration": random.uniform(0.5, 3.0),
                }
                for i in range(min(10, self._tick_count // 5))
            ],
        }

    # ── Updates widgets ───────────────────────────────────────────────────────

    def _update_pipeline(self, state: dict) -> None:
        pipeline = self.query_one("#pipeline", PipelineStages)
        pipeline.update_counts(
            events=state.get("event_count", 0),
            intents=state.get("intent_count", 0),
            tasks=state.get("task_count", 0),
            completed=state.get("completed_count", 0),
        )

    def _update_task_detail(self, state: dict) -> None:
        detail = self.query_one("#task-detail", TaskDetail)
        active = state.get("active_task", {})
        detail.update_task(active)

    def _update_history(self, state: dict) -> None:
        history = self.query_one("#task-history", TaskHistory)
        tasks = state.get("recent_tasks", [])
        history.update_history(tasks)

    def _update_status_bar(self) -> None:
        status = self.query_one("#status-bar", Static)
        pause_icon = ICONS["paused"] if self.paused else ICONS["running"]
        fps = 1.0 / self.refresh_rate if self.refresh_rate > 0 else 0
        status.update(
            f"  {pause_icon} {'PAUSED' if self.paused else 'LIVE'}  |  "
            f"FPS: {fps:.0f}  |  Ticks: {self._tick_count}  |  "
            f"[SPACE] pause  [R] refresh  [Q] quit"
        )

    # ── Actions ───────────────────────────────────────────────────────────────

    def action_toggle_pause(self) -> None:
        """Toggle pause/resume."""
        self.paused = not self.paused
        self._update_status_bar()
        state = "paused" if self.paused else "resumed"
        self.notify(f"GraphView {state}", timeout=1)

    def action_refresh_now(self) -> None:
        """Force un refresh immédiat."""
        self._tick()
        self.notify("Refreshed", timeout=1)

    def action_clear_history(self) -> None:
        """Efface l'historique."""
        history = self.query_one("#task-history", TaskHistory)
        history.update_history([])
        self.notify("History cleared", timeout=1)


# ─── Export ───────────────────────────────────────────────────────────────────

__all__ = [
    "GraphViewScreen",
    "PipelineStages",
    "TaskDetail",
    "TaskHistory",
]
