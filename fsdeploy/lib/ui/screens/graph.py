# -*- coding: utf-8 -*-
"""
fsdeploy.ui.screens.graph
===========================
Ecran GraphView : etat temps reel du scheduler.
Compatible : Textual >=8.2.1
"""

import os
from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Label, ProgressBar, Static

IS_FB = os.environ.get("TERM") == "linux"
ICONS = {
    "pending": "[.]" if IS_FB else "\u23f3",
    "running": "[>]" if IS_FB else "\U0001f504",
    "completed": "[+]" if IS_FB else "\u2705",
    "failed": "[X]" if IS_FB else "\u274c",
    "arrow": "->" if IS_FB else "\u2192",
}


class GraphScreen(Screen):

    BINDINGS = [
        Binding("r", "refresh", "Rafraichir", show=True),
        Binding("space", "toggle_pause", "Pause", show=True),
        Binding("escape", "app.pop_screen", "Retour", show=False),
    ]

    DEFAULT_CSS = """
    GraphScreen { layout: vertical; }
    #graph-header { height: auto; padding: 1 2; text-style: bold; }
    #pipeline { height: 3; padding: 0 2; text-style: bold; }
    #task-detail { height: auto; min-height: 4; margin: 0 1;
                   border: solid $accent; padding: 1 2; }
    #history-section { height: 1fr; margin: 0 1;
                       border: solid $primary; padding: 0 1; }
    .table-title { text-style: bold; height: 1; }
    #status-bar { dock: bottom; height: 1; background: $primary-background;
                  color: $text-muted; padding: 0 2; }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._paused = False
        self._timer = None

    @property
    def bridge(self):
        return getattr(self.app, "bridge", None)

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Pipeline Scheduler", id="graph-header")
        yield Static("", id="pipeline")
        yield Static("Aucune tache active", id="task-detail")
        with Vertical(id="history-section"):
            yield Label("Taches recentes", classes="table-title")
            yield DataTable(id="history-table")
        yield Static("Mode : LIVE | Pause : Space", id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        from fsdeploy.lib.ui.bridge import SchedulerBridge
        self.bridge = SchedulerBridge.default()
        table = self.query_one("#history-table", DataTable)
        table.add_columns("Statut", "Tache", "Duree")
        table.cursor_type = "row"
        self._timer = self.set_interval(1.0, self._update_data)
        self._update_data()

    def on_unmount(self) -> None:
        if self._timer:
            self._timer.stop()

    def action_refresh(self) -> None:
        self._update_data()

    def action_toggle_pause(self) -> None:
        self._paused = not self._paused
        mode = "PAUSED" if self._paused else "LIVE"
        try:
            self.query_one("#status-bar", Static).update(
                f"Mode : {mode} | Pause : Space"
            )
        except Exception:
            pass

    def _update_data(self) -> None:
        if self._paused:
            return
        if not self.bridge:
            return
        state = self.bridge.get_scheduler_state()
        self._update_pipeline(state)
        self._update_task_detail(state)
        self._update_history(state)

    def _update_pipeline(self, state: dict) -> None:
        arrow = ICONS["arrow"]
        p = ICONS["pending"]
        r = ICONS["running"]
        d = ICONS["completed"]
        ec = state.get("event_count", 0)
        ic = state.get("intent_count", 0)
        tc = state.get("task_count", 0)
        cc = state.get("completed_count", 0)
        text = (
            f"  [{p} Events: {ec}] {arrow} "
            f"[{p} Intents: {ic}] {arrow} "
            f"[{r} Tasks: {tc}] {arrow} "
            f"[{d} Done: {cc}]"
        )
        try:
            self.query_one("#pipeline", Static).update(text)
        except Exception:
            pass

    def _update_task_detail(self, state: dict) -> None:
        active = state.get("active_task")
        if not active:
            text = "  Aucune tache active"
        else:
            name = active.get("name", active.get("id", "?"))
            status = active.get("status", "?")
            progress = active.get("progress", 0)
            duration = active.get("duration", 0)
            icon = ICONS.get(status, "[?]")
            text = (
                f"  {icon} {name}\n"
                f"  Statut: {status} ({progress}%) | Duree: {duration:.1f}s"
            )
        try:
            self.query_one("#task-detail", Static).update(text)
        except Exception:
            pass

    def _update_history(self, state: dict) -> None:
        recent = state.get("recent_tasks", [])
        try:
            table = self.query_one("#history-table", DataTable)
            table.clear()
            for task in recent[-10:]:
                status = task.get("status", "?")
                icon = ICONS.get(status, "[?]")
                name = task.get("name", task.get("id", "?"))
                duration = task.get("duration", 0)
                table.add_row(icon, name, f"{duration:.1f}s")
        except Exception:
            pass

    def update_from_snapshot(self, snapshot: Any) -> None:
        pass
