"""
fsdeploy.ui.screens.snapshots
================================
Gestion des snapshots ZFS — 100% bus events.

Compatible : Textual >=8.2.1 / Rich >=14.3.3

Changement Textual 8.x :
  - on_data_table_row_selected → on_data_table_row_highlighted
    (RowSelected n'est emis qu'au 2eme clic en 8.x)
"""

import os
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Input, Label, Log, Static

IS_FB = os.environ.get("TERM") == "linux"
CHECK, CROSS, WARN, ARROW = (
    ("[OK]", "[!!]", "[??]", "->") if IS_FB
    else ("✅", "❌", "⚠️", "→")
)

class SnapshotsScreen(Screen):
    BINDINGS = [
        Binding("r", "refresh", "Rafraichir", show=True),
        Binding("c", "create_snapshot", "Creer", show=True),
        Binding("escape", "app.pop_screen", "Retour", show=False),
    ]
    DEFAULT_CSS = """
    SnapshotsScreen { layout: vertical; }
    #snap-header { height: auto; padding: 1 2; text-style: bold; }
    #snap-status { padding: 0 2; height: 1; color: $text-muted; }
    #snap-table-section { height: 1fr; margin: 0 1; border: solid $primary; padding: 0 1; }
    #create-row { height: 3; padding: 0 2; layout: horizontal; }
    #create-row Input { width: 1fr; margin: 0 1; }
    #create-row Button { margin: 0 1; }
    #command-log { height: 6; margin: 0 1; border: solid $primary-background; padding: 0 1; }
    #action-buttons { height: 3; padding: 0 2; layout: horizontal; }
    #action-buttons Button { margin: 0 1; }
    """

    def __init__(self, **kw):
        super().__init__(**kw)
        self._snaps: list[dict] = []
        self._sel: int = -1

    @property
    def bridge(self):
        return getattr(self.app, "bridge", None)

    def compose(self) -> ComposeResult:
        yield Static("Snapshots ZFS", id="snap-header")
        yield Static("Statut : chargement...", id="snap-status")
        with Vertical(id="snap-table-section"):
            yield Label("Snapshots")
            yield DataTable(id="snap-table")
        with Horizontal(id="create-row"):
            yield Label("Dataset :")
            yield Input(id="input-dataset", placeholder="pool/dataset")
            yield Label("Nom :")
            yield Input(id="input-snap-name", placeholder="(auto)")
            yield Button("Creer", variant="primary", id="btn-create")
        yield Log(id="command-log", highlight=True, auto_scroll=True)
        with Horizontal(id="action-buttons"):
            yield Button("Rafraichir", id="btn-refresh")
            yield Button("Rollback", variant="error", id="btn-rollback")

    def on_mount(self):
        from fsdeploy.lib.ui.bridge import SchedulerBridge
        self.bridge = SchedulerBridge.default()
        dt = self.query_one("#snap-table", DataTable)
        dt.add_columns("Snapshot", "Utilise", "Creation")
        dt.cursor_type = "row"
        self._refresh()

    def _refresh(self):
        if not self.bridge:
            return
        self.bridge.emit("snapshot.list", callback=self._on_list)

    def _on_list(self, t):
        if t.status == "completed" and isinstance(t.result, list):
            self._snaps = t.result
            self._safe(self._refresh_table)
            self._safe(lambda: self._status(f"{CHECK} {len(self._snaps)} snapshots"))

    def _refresh_table(self):
        dt = self.query_one("#snap-table", DataTable)
        dt.clear()
        for s in self._snaps:
            dt.add_row(
                s.get("name", "?"),
                s.get("used", "?"),
                s.get("creation", "?"),
            )

    # Textual 8.x : RowHighlighted au lieu de RowSelected
    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.cursor_row is not None:
            self._sel = event.cursor_row

    def on_button_pressed(self, e):
        bid = e.button.id or ""
        if bid == "btn-refresh":
            self._refresh()
        elif bid == "btn-create":
            self.action_create_snapshot()
        elif bid == "btn-rollback":
            self._rollback()

    def action_create_snapshot(self):
        if not self.bridge:
            return
        ds = self.query_one("#input-dataset", Input).value.strip()
        name = self.query_one("#input-snap-name", Input).value.strip()
        if not ds:
            self.notify("Dataset requis.", severity="warning")
            return
        self.bridge.emit(
            "snapshot.create", dataset=ds, name=name,
            callback=lambda t: (
                self._safe(self._refresh) if t.status == "completed"
                else self._slog(f"{CROSS} {t.error}")
            ),
        )
        self._log(f"-> snapshot.create({ds})")

    def _rollback(self):
        if self._sel < 0 or self._sel >= len(self._snaps) or not self.bridge:
            return
        snap = self._snaps[self._sel].get("name", "")
        self.bridge.emit(
            "snapshot.rollback", snapshot=snap, confirmed=True,
            callback=lambda t: self._slog(
                f"{CHECK} Rollback {snap}" if t.status == "completed"
                else f"{CROSS} {t.error}"
            ),
        )

    def action_refresh(self):
        self._refresh()

    def update_from_snapshot(self, s):
        pass

    def _log(self, m):
        try:
            self.query_one("#command-log", Log).write_line(m)
        except Exception:
            pass

    def _slog(self, m):
        try:
            self.app.call_from_thread(self._log, m)
        except Exception:
            self._log(m)

    def _status(self, t):
        try:
            self.query_one("#snap-status", Static).update(f"Statut : {t}")
        except Exception:
            pass

    def _safe(self, fn):
        try:
            self.app.call_from_thread(fn)
        except Exception:
            fn()
