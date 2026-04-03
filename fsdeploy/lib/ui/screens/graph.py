"""
fsdeploy.ui.screens.graph — Unified GraphViewScreen.
Compatible : Textual >=8.2.1 / Rich >=14.3.3
"""
import os
from datetime import datetime
from typing import Any, Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Label, Rule, Static
from textual.reactive import reactive
from textual.timer import Timer

IS_FB = os.environ.get("TERM") == "linux"
ARROW = "->" if IS_FB else "→"
PENDING = "[.]" if IS_FB else "⏳"
RUNNING = "[*]" if IS_FB else "🔄"
COMPLETED = "[+]" if IS_FB else "✅"
FAILED = "[X]" if IS_FB else "❌"
PAUSED = "[-]" if IS_FB else "⏸️"

class PipelineStages(Static):
    DEFAULT_CSS = "PipelineStages { height: auto; padding: 1 2; }"
    event_count: reactive[int] = reactive(0)
    intent_count: reactive[int] = reactive(0)
    task_count: reactive[int] = reactive(0)
    completed_count: reactive[int] = reactive(0)
    _animation_frame: reactive[int] = reactive(0)

    def render(self) -> str:
        frames = [ARROW, f" {ARROW}", f"  {ARROW}", f" {ARROW}"]
        anim = frames[self._animation_frame % len(frames)]
        return (f"  [{PENDING} EventQueue: {self.event_count}] {anim} "
                f"[{PENDING} IntentQueue: {self.intent_count}] {anim} "
                f"[{RUNNING} TaskGraph: {self.task_count}] {anim} "
                f"[{COMPLETED} Done: {self.completed_count}]")

    def update_counts(self, event=0, intent=0, task=0, completed=0):
        self.event_count = event; self.intent_count = intent
        self.task_count = task; self.completed_count = completed

    def animate_arrows(self): self._animation_frame += 1

class TaskDetail(Static):
    DEFAULT_CSS = "TaskDetail { height: auto; min-height: 5; padding: 1 2; border: solid $accent; }"
    def __init__(self, **kw): super().__init__(**kw); self._task_data = {}
    def update_task(self, d): self._task_data = d; self.refresh()
    def clear(self): self._task_data = {}; self.refresh()
    def render(self) -> str:
        if not self._task_data: return "  Aucune tache active"
        t = self._task_data; p = t.get("progress", 0); bw = 30
        bar = "#" * int(bw * p / 100) + "-" * (bw - int(bw * p / 100))
        icon = {
            "running": RUNNING, "completed": COMPLETED, "failed": FAILED
        }.get(t.get("status",""), PENDING)
        return "\n".join([
            f"  {icon} {t.get('name', t.get('type', '?'))}",
            f"  Status    : {t.get('status','?').upper()} ({p}%)",
            f"  [{bar}]",
            f"  Thread    : {t.get('thread_id','?')}/{t.get('max_threads','?')}",
            f"  Duration  : {t.get('duration',0):.1f}s",
            f"  Lock      : {t.get('lock','none')}",
        ])

class TaskHistory(DataTable):
    DEFAULT_CSS = "TaskHistory { height: 1fr; }"
    def __init__(self, **kw): super().__init__(**kw); self.cursor_type="row"; self._ids=set()
    def on_mount(self): self.add_columns("Status", "Task", "Duration")
    def add_task(self, task):
        tid = task.get("id","?")
        if tid in self._ids: return
        self._ids.add(tid)
        s = task.get("status","unknown")
        icon = {"running":RUNNING,"completed":COMPLETED,"failed":FAILED}.get(s, PENDING)
        n = task.get("type", task.get("name","")) or tid
        d = f"{task.get('duration',0):.1f}s" if s == "completed" else s
        self.add_row(icon, f"{n} ({tid})", d)
    def clear_history(self): self._ids.clear(); self.clear()

class GraphViewScreen(Screen):
    BINDINGS = [
        Binding("g", "app.pop_screen", "Fermer", show=True),
        Binding("escape", "app.pop_screen", "Retour", show=False),
        Binding("space", "toggle_pause", "Pause/Resume", show=True),
        Binding("r", "reset_view", "Reset", show=True),
        Binding("left", "nav_hist", "Historique", show=True),
        Binding("right", "nav_future", "Futur", show=True),
    ]
    DEFAULT_CSS = """
    GraphViewScreen { layout: vertical; }
    #graph-header { height: auto; padding: 1 2; text-style: bold; background: $boost; }
    #graph-status { height: 1; padding: 0 2; color: $text-muted; }
    #pipeline-stages { height: auto; }
    #task-detail { height: auto; }
    #task-history { height: 1fr; }
    #controls { height: 2; padding: 0 2; color: $text-muted; }
    """
    def __init__(self, **kw):
        super().__init__(**kw); self.name = "graph"
        self._paused = False; self._offset = 0
        self._anim_timer = None; self._data_timer = None

    @property
    def bridge(self): return getattr(self.app, "bridge", None)

    def compose(self) -> ComposeResult:
        yield Static("Pipeline Execution — Temps reel", id="graph-header")
        yield Static("", id="graph-status")
        yield PipelineStages(id="pipeline-stages"); yield Rule()
        yield Label("Tache active", classes="section-title")
        yield TaskDetail(id="task-detail"); yield Rule()
        yield Label("Historique", classes="section-title")
        yield TaskHistory(id="task-history")
        yield Static("  [Space] Pause  [R] Reset  [G/Esc] Fermer", id="controls")

    def on_mount(self):
        self._anim_timer = self.set_interval(0.1, self._animate)
        self._data_timer = self.set_interval(0.2, self._update_data)
        self._update_bar()

    def on_unmount(self):
        if self._anim_timer: self._anim_timer.stop()
        if self._data_timer: self._data_timer.stop()

    def _animate(self):
        if self._paused: return
        try: self.query_one("#pipeline-stages", PipelineStages).animate_arrows()
        except: pass

    def _update_data(self):
        if self._paused: return
        state = self._get_state()
        try:
            s = self.query_one("#pipeline-stages", PipelineStages)
            s.update_counts(event=state.get("event_count",0), intent=state.get("intent_count",0),
                           task=state.get("task_count",0), completed=state.get("completed_count",0))
        except: pass
        try:
            d = self.query_one("#task-detail", TaskDetail)
            at = state.get("active_task")
            d.update_task(at) if at else d.clear()
        except: pass
        try:
            h = self.query_one("#task-history", TaskHistory)
            for t in state.get("recent_tasks", []): h.add_task(t)
        except: pass
        self._update_bar()

    def _get_state(self) -> dict:
        if self.bridge and hasattr(self.bridge, "get_scheduler_state"):
            try: return self.bridge.get_scheduler_state()
            except: pass
        import random
        return {"event_count": random.randint(0,5), "intent_count": random.randint(0,3),
                "task_count": random.randint(0,2), "completed_count": random.randint(10,50),
                "active_task": {"id":"probe_boot","name":"DatasetProbeTask","status":"running",
                    "progress":random.randint(0,100),"thread_id":2,"max_threads":4,
                    "duration":random.random()*5,"lock":"pool.boot.probe"} if random.random()>0.3 else None,
                "recent_tasks": []}

    def _update_bar(self):
        now = datetime.now().strftime("%H:%M:%S")
        p = f" {PAUSED} PAUSED" if self._paused else ""
        o = f" [offset: {self._offset}]" if self._offset else ""
        try: self.query_one("#graph-status", Static).update(f"  {now}{p}{o}")
        except: pass

    def action_toggle_pause(self): self._paused = not self._paused; self._update_bar()
    def action_reset_view(self):
        self._offset = 0; self._paused = False
        try: self.query_one("#task-history", TaskHistory).clear_history()
        except: pass
        self._update_bar()
    def action_nav_hist(self): self._offset -= 1; self._update_bar()
    def action_nav_future(self):
        if self._offset < 0: self._offset += 1
        self._update_bar()
    def update_from_snapshot(self, s): pass
