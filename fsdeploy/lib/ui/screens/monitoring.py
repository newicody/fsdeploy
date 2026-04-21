# -*- coding: utf-8 -*-
"""
fsdeploy.ui.screens.monitoring
=================================
Tableau de bord de monitoring des taches.
Compatible : Textual >=8.2.1
"""

import os
from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Label, Static

IS_FB = os.environ.get("TERM") == "linux"
ICONS = {
    "pending": "[.]" if IS_FB else "\u23f3",
    "running": "[>]" if IS_FB else "\U0001f504",
    "completed": "[+]" if IS_FB else "\u2705",
    "failed": "[X]" if IS_FB else "\u274c",
}


class MonitoringScreen(Screen):

    BINDINGS = [
        Binding("r", "refresh", "Rafraichir", show=True),
        Binding("space", "toggle_pause", "Pause", show=True),
        Binding("escape", "app.pop_screen", "Retour", show=False),
    ]

    DEFAULT_CSS = """
    MonitoringScreen { layout: vertical; }
    #mon-header { height: auto; padding: 1 2; text-style: bold; }
    #mon-stats { height: 2; padding: 0 2; }
    #task-section { height: 1fr; margin: 0 1; border: solid $primary; padding: 0 1; }
    .table-title { text-style: bold; height: 1; }
    #mon-status { dock: bottom; height: 1; background: $primary-background;
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
        yield Static("Monitoring", id="mon-header")
        yield Static("", id="mon-stats")
        with Vertical(id="task-section"):
            yield Label("Taches recentes", classes="table-title")
            yield DataTable(id="task-table")
        yield Static("Mode : LIVE | Pause : Space", id="mon-status")
        yield Footer()

    def on_mount(self) -> None:
        from fsdeploy.lib.ui.bridge import SchedulerBridge
        self.bridge = SchedulerBridge.default()
        table = self.query_one("#task-table", DataTable)
        table.add_columns("Statut", "Tache", "Duree")
        table.cursor_type = "row"
        self._timer = self.set_interval(5.0, self._update_data)
        self._update_data()

    def on_unmount(self) -> None:
        if self._timer:
            self._timer.stop()

    def action_refresh(self) -> None:
        self._update_data()
        self.notify("Monitoring actualise", timeout=2)

    def action_toggle_pause(self) -> None:
        self._paused = not self._paused
        mode = "PAUSED" if self._paused else "LIVE"
        try:
            self.query_one("#mon-status", Static).update(
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
        self._update_stats(state)
        self._update_table(state)

    def _update_stats(self, state: dict) -> None:
        ec = state.get("event_count", 0)
        ic = state.get("intent_count", 0)
        tc = state.get("task_count", 0)
        cc = state.get("completed_count", 0)
        text = (
            f"  Events: {ec} | Intents: {ic} | "
            f"Tasks actives: {tc} | Completees: {cc}"
        )
        try:
            self.query_one("#mon-stats", Static).update(text)
        except Exception:
            pass

    def _update_table(self, state: dict) -> None:
        recent = state.get("recent_tasks", [])
        active = state.get("active_task")
        try:
            table = self.query_one("#task-table", DataTable)
            table.clear()
            if active:
                name = active.get("name", active.get("id", "?"))
                duration = active.get("duration", 0)
                table.add_row(ICONS["running"], name, f"{duration:.1f}s")
            for task in recent[-10:]:
                status = task.get("status", "completed")
                icon = ICONS.get(status, "[?]")
                name = task.get("name", task.get("id", "?"))
                duration = task.get("duration", 0)
                table.add_row(icon, name, f"{duration:.1f}s")
        except Exception:
            pass

    def update_from_snapshot(self, snapshot: Any) -> None:
        pass
