"""
fsdeploy.ui.screens.graph
===========================
GraphViewScreen — Visualisation temps réel animée du pipeline.

Affiche Event → Intent → Task avec animation, auto-centrage, navigation temps.
"""

import os
from datetime import datetime
from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import (
    Button, DataTable, Footer, Header, Label, ProgressBar, Rule, Static,
)
from textual.reactive import reactive
from textual import events
from textual.timer import Timer


IS_FB = os.environ.get("TERM") == "linux"

# ═══════════════════════════════════════════════════════════════════
# SYMBOLS (ASCII fallback pour framebuffer)
# ═══════════════════════════════════════════════════════════════════

if IS_FB:
    ARROW = "->"
    PENDING = "[.]"
    RUNNING = "[*]"
    COMPLETED = "[+]"
    FAILED = "[X]"
    PAUSED = "[-]"
else:
    ARROW = "→"
    PENDING = "⏳"
    RUNNING = "🔄"
    COMPLETED = "✅"
    FAILED = "❌"
    PAUSED = "⏸️"


# ═══════════════════════════════════════════════════════════════════
# PIPELINE STAGES WIDGET
# ═══════════════════════════════════════════════════════════════════

class PipelineStages(Static):
    """Widget affichant les étapes du pipeline avec compteurs."""
    
    DEFAULT_CSS = """
    PipelineStages {
        height: 3;
        border: solid $primary;
        padding: 0 2;
    }
    
    .stage-container {
        layout: horizontal;
        height: 100%;
        align: center middle;
    }
    
    .stage {
        padding: 0 2;
        text-align: center;
    }
    
    .stage-name {
        text-style: bold;
    }
    
    .stage-count {
        color: $text-muted;
    }
    
    .arrow {
        padding: 0 1;
        color: $accent;
    }
    """
    
    # Reactive counts
    event_count = reactive(0)
    intent_count = reactive(0)
    task_count = reactive(0)
    completed_count = reactive(0)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._animate_arrow = True
        self._arrow_frame = 0
    
    def compose(self) -> ComposeResult:
        with Horizontal(classes="stage-container"):
            yield Static("[EventQueue]", classes="stage stage-name")
            yield Static(f"{PENDING} 0", id="event-count", classes="stage-count")
            
            yield Static(ARROW, id="arrow1", classes="arrow")
            
            yield Static("[IntentQueue]", classes="stage stage-name")
            yield Static(f"{PENDING} 0", id="intent-count", classes="stage-count")
            
            yield Static(ARROW, id="arrow2", classes="arrow")
            
            yield Static("[TaskGraph]", classes="stage stage-name")
            yield Static(f"{RUNNING} 0", id="task-count", classes="stage-count")
            
            yield Static(ARROW, id="arrow3", classes="arrow")
            
            yield Static("[Completed]", classes="stage stage-name")
            yield Static(f"{COMPLETED} 0", id="completed-count", classes="stage-count")
    
    def update_counts(self, event: int, intent: int, task: int, completed: int):
        """Met à jour les compteurs."""
        self.event_count = event
        self.intent_count = intent
        self.task_count = task
        self.completed_count = completed
        
        self.query_one("#event-count", Static).update(f"{PENDING} {event}")
        self.query_one("#intent-count", Static).update(f"{PENDING} {intent}")
        self.query_one("#task-count", Static).update(f"{RUNNING} {task}")
        self.query_one("#completed-count", Static).update(f"{COMPLETED} {completed}")
    
    def animate_arrows(self):
        """Anime les flèches (appelé par timer)."""
        if not self._animate_arrow:
            return
        
        # Cycle d'animation : → → → → (4 frames)
        self._arrow_frame = (self._arrow_frame + 1) % 4
        
        if IS_FB:
            arrows = ["-", "->", "-->", "--->"]
        else:
            arrows = ["→", "→→", "→→→", "→→→→"]
        
        arrow_text = arrows[self._arrow_frame]
        
        for arrow_id in ["arrow1", "arrow2", "arrow3"]:
            try:
                self.query_one(f"#{arrow_id}", Static).update(arrow_text)
            except:
                pass


# ═══════════════════════════════════════════════════════════════════
# TASK DETAIL WIDGET
# ═══════════════════════════════════════════════════════════════════

class TaskDetail(Static):
    """Widget affichant les détails d'une tâche en cours."""
    
    DEFAULT_CSS = """
    TaskDetail {
        height: auto;
        min-height: 10;
        border: solid $warning;
        padding: 1 2;
        margin: 0 1;
    }
    
    .task-header {
        text-style: bold;
        padding: 0 0 1 0;
    }
    
    .task-field {
        padding: 0 0 0 2;
    }
    
    .task-progress {
        padding: 1 0;
    }
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._task_data = None
    
    def compose(self) -> ComposeResult:
        yield Label("No active task", id="task-header", classes="task-header")
        yield Label("", id="task-status", classes="task-field")
        yield Label("", id="task-thread", classes="task-field")
        yield Label("", id="task-duration", classes="task-field")
        yield Label("", id="task-lock", classes="task-field")
        yield ProgressBar(id="task-progress", total=100)
    
    def update_task(self, task_data: dict):
        """Met à jour l'affichage avec les données de tâche."""
        self._task_data = task_data
        
        # Header avec icône de statut
        status = task_data.get("status", "unknown")
        icon = {
            "pending": PENDING,
            "running": RUNNING,
            "completed": COMPLETED,
            "failed": FAILED,
            "paused": PAUSED,
        }.get(status, "?")
        
        name = task_data.get("name", "Unknown")
        header = f"{icon} {name}"
        
        self.query_one("#task-header", Label).update(header)
        
        # Champs
        self.query_one("#task-status", Label).update(
            f"Status    : {status.upper()} ({task_data.get('progress', 0)}%)"
        )
        
        thread_id = task_data.get("thread_id", "N/A")
        max_threads = task_data.get("max_threads", 4)
        self.query_one("#task-thread", Label).update(
            f"Thread    : {thread_id}/{max_threads}"
        )
        
        duration = task_data.get("duration", 0.0)
        self.query_one("#task-duration", Label).update(
            f"Duration  : {duration:.1f}s"
        )
        
        lock = task_data.get("lock", "none")
        self.query_one("#task-lock", Label).update(
            f"Lock      : {lock}"
        )
        
        # Progress bar
        progress = task_data.get("progress", 0)
        self.query_one("#task-progress", ProgressBar).update(progress=progress)
    
    def clear(self):
        """Efface l'affichage."""
        self.query_one("#task-header", Label).update("No active task")
        self.query_one("#task-status", Label).update("")
        self.query_one("#task-thread", Label).update("")
        self.query_one("#task-duration", Label).update("")
        self.query_one("#task-lock", Label).update("")
        self.query_one("#task-progress", ProgressBar).update(progress=0)


# ═══════════════════════════════════════════════════════════════════
# TASK HISTORY WIDGET
# ═══════════════════════════════════════════════════════════════════

class TaskHistory(Static):
    """Widget affichant l'historique des tâches."""
    
    DEFAULT_CSS = """
    TaskHistory {
        height: 1fr;
        border: solid $primary-background;
        padding: 0 1;
    }
    
    #history-table {
        height: 100%;
    }
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._history = []
        self._selected_idx = -1
    
    def compose(self) -> ComposeResult:
        yield DataTable(id="history-table", cursor_type="row")
    
    def on_mount(self):
        """Initialise la table."""
        dt = self.query_one("#history-table", DataTable)
        dt.add_columns("Status", "Task", "Duration")
        dt.zebra_stripes = True
    
    def add_task(self, task_data: dict):
        """Ajoute une tâche à l'historique."""
        self._history.append(task_data)
        
        # Limiter à 100 entrées
        if len(self._history) > 100:
            self._history.pop(0)
        
        self._refresh_table()
    
    def update_task(self, task_id: str, updates: dict):
        """Met à jour une tâche existante."""
        for task in self._history:
            if task.get("id") == task_id:
                task.update(updates)
                break
        
        self._refresh_table()
    
    def _refresh_table(self):
        """Rafraîchit l'affichage de la table."""
        dt = self.query_one("#history-table", DataTable)
        dt.clear()
        
        # Afficher les 10 dernières tâches
        recent = self._history[-10:]
        
        for task in recent:
            status = task.get("status", "unknown")
            icon = {
                "pending": PENDING,
                "running": RUNNING,
                "completed": COMPLETED,
                "failed": FAILED,
            }.get(status, "?")
            
            name = task.get("name", "Unknown")
            duration = task.get("duration", 0.0)
            
            if status == "running":
                duration_str = "running"
            else:
                duration_str = f"{duration:.1f}s"
            
            dt.add_row(icon, name, duration_str)
    
    def get_history(self) -> list[dict]:
        """Retourne l'historique complet."""
        return self._history.copy()


# ═══════════════════════════════════════════════════════════════════
# GRAPH VIEW SCREEN
# ═══════════════════════════════════════════════════════════════════

class GraphViewScreen(Screen):
    """
    Écran de visualisation temps réel du pipeline.
    
    Fonctionnalités :
    - Animation temps réel (flèches animées)
    - Auto-centrage sur tâche active
    - Zoom + info détaillée
    - Navigation temps (historique ← → futur)
    - Couleurs par statut
    - Responsive
    """
    
    BINDINGS = [
        Binding("g", "app.pop_screen", "Fermer GraphView", show=True),
        Binding("escape", "app.pop_screen", "Retour", show=False),
        Binding("space", "toggle_pause", "Pause/Resume", show=True),
        Binding("r", "reset_view", "Reset", show=True),
        Binding("c", "center_active", "Center", show=True),
        Binding("z", "toggle_zoom", "Zoom", show=True),
        Binding("left", "navigate_history", "← Historique", show=True),
        Binding("right", "navigate_future", "→ Futur", show=True),
    ]
    
    DEFAULT_CSS = """
    GraphViewScreen {
        layout: vertical;
    }
    
    #graph-header {
        height: auto;
        padding: 1 2;
        text-style: bold;
        background: $boost;
    }
    
    #graph-status {
        height: 1;
        padding: 0 2;
        color: $text-muted;
    }
    
    #pipeline-stages {
        height: auto;
    }
    
    #task-detail {
        height: auto;
    }
    
    #task-history {
        height: 1fr;
    }
    
    #controls {
        height: 2;
        padding: 0 2;
        color: $text-muted;
    }
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = "graph"
        
        self._paused = False
        self._zoomed = False
        self._history_offset = 0  # 0 = présent, <0 = passé, >0 = futur
        
        self._animation_timer = None
        self._update_timer = None
    
    @property
    def bridge(self):
        """Accès au bridge scheduler."""
        return getattr(self.app, "bridge", None)
    
    # ── Compose ─────────────────────────────────────────────────────
    
    def compose(self) -> ComposeResult:
        yield Header()
        
        yield Static("Pipeline Execution — Temps réel", id="graph-header")
        yield Static("Mode : LIVE | Offset : 0 | FPS : 10", id="graph-status")
        
        yield Rule()
        
        yield PipelineStages(id="pipeline-stages")
        
        yield Rule()
        
        yield TaskDetail(id="task-detail")
        
        yield Rule()
        
        with VerticalScroll(id="task-history"):
            yield TaskHistory()
        
        yield Rule()
        
        yield Static(
            "Timeline : [←] Historique  [→] Futur  [Space] Pause  "
            "[z] Zoom  [c] Center  [r] Reset  [Esc] Retour",
            id="controls"
        )
        
        yield Footer()
    
    # ── Lifecycle ───────────────────────────────────────────────────
    
    def on_mount(self):
        """Démarrage des timers d'animation."""
        # Animation flèches : 10 FPS (100ms)
        self._animation_timer = self.set_interval(0.1, self._animate)
        
        # Mise à jour données : 5 FPS (200ms)
        self._update_timer = self.set_interval(0.2, self._update_data)
    
    def on_unmount(self):
        """Arrêt des timers."""
        if self._animation_timer:
            self._animation_timer.stop()
        if self._update_timer:
            self._update_timer.stop()
    
    # ── Animation ───────────────────────────────────────────────────
    
    def _animate(self):
        """Animation des flèches (appelée par timer 10 FPS)."""
        if self._paused:
            return
        
        stages = self.query_one("#pipeline-stages", PipelineStages)
        stages.animate_arrows()
    
    def _update_data(self):
        """Mise à jour des données depuis le scheduler (5 FPS)."""
        if self._paused or not self.bridge:
            return
        
        # Récupérer état du scheduler via bridge
        state = self._get_scheduler_state()
        
        # Mettre à jour les compteurs
        stages = self.query_one("#pipeline-stages", PipelineStages)
        stages.update_counts(
            event=state.get("event_count", 0),
            intent=state.get("intent_count", 0),
            task=state.get("task_count", 0),
            completed=state.get("completed_count", 0),
        )
        
        # Mettre à jour tâche active
        active_task = state.get("active_task")
        detail = self.query_one("#task-detail", TaskDetail)
        
        if active_task:
            detail.update_task(active_task)
            
            # Auto-center si pas en mode historique
            if self._history_offset == 0:
                self._center_on_task(active_task)
        else:
            detail.clear()
        
        # Mettre à jour historique
        history_widget = self.query_one(TaskHistory)
        for task in state.get("recent_tasks", []):
            history_widget.add_task(task)
        
        # Mettre à jour status bar
        self._update_status_bar()
    
    def _get_scheduler_state(self) -> dict:
        """Récupère l'état du scheduler via bridge."""
        if not self.bridge:
            return {}
        
        # TODO: Appeler bridge.get_state() ou similaire
        # Pour l'instant, retourne des données de démo
        
        import random
        
        return {
            "event_count": random.randint(0, 5),
            "intent_count": random.randint(0, 3),
            "task_count": random.randint(0, 2),
            "completed_count": random.randint(10, 50),
            "active_task": {
                "id": "probe_boot",
                "name": "DatasetProbeTask (boot_pool/boot)",
                "status": "running",
                "progress": random.randint(0, 100),
                "thread_id": 2,
                "max_threads": 4,
                "duration": random.random() * 5,
                "lock": "pool.boot_pool.probe",
            } if random.random() > 0.3 else None,
            "recent_tasks": [],
        }
    
    # ── Actions ─────────────────────────────────────────────────────
    
    def action_toggle_pause(self):
        """Pause/Resume l'animation."""
        self._paused = not self._paused
        self._update_status_bar()
    
    def action_reset_view(self):
        """Reset la vue (offset=0, zoom=1)."""
        self._history_offset = 0
        self._zoomed = False
        self._update_status_bar()
    
    def action_center_active(self):
        """Centre la vue sur la tâche active."""
        if not self.bridge:
            return
        
        state = self._get_scheduler_state()
        active_task = state.get("active_task")
        
        if active_task:
            self._center_on_task(active_task)
    
    def action_toggle_zoom(self):
        """Toggle zoom in/out."""
        self._zoomed = not self._zoomed
        # TODO: Implémenter zoom visuel
        self._update_status_bar()
    
    def action_navigate_history(self):
        """Navigate vers le passé (historique)."""
        self._history_offset -= 1
        self._update_status_bar()
        # TODO: Charger tâches du passé
    
    def action_navigate_future(self):
        """Navigate vers le futur (pending tasks)."""
        if self._history_offset < 0:
            self._history_offset += 1
        self._update_status_bar()
        # TODO: Charger tâches futures
    
    # ── Helpers ─────────────────────────────────────────────────────
    
    def _center_on_task(self, task_data: dict):
        """Centre la vue sur une tâche."""
        # TODO: Scroll automatique vers la tâche
        pass
    
    def _update_status_bar(self):
        """Met à jour la barre de statut."""
        mode = "PAUSED" if self._paused else "LIVE"
        zoom = "2x" if self._zoomed else "1x"
        offset_str = f"{self._history_offset:+d}" if self._history_offset != 0 else "0"
        
        status = f"Mode : {mode} | Offset : {offset_str} | Zoom : {zoom} | FPS : 10"
        
        self.query_one("#graph-status", Static).update(status)


# ═══════════════════════════════════════════════════════════════════
# EXEMPLE D'UTILISATION
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    from textual.app import App
    
    class GraphViewApp(App):
        def on_mount(self):
            self.push_screen(GraphViewScreen())
    
    app = GraphViewApp()
    app.run()
