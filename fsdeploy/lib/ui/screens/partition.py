"""
fsdeploy.ui.screens.partition — Gestion des partitions, 100% bus events.
"""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Label, Log, Static

class PartitionScreen(Screen):
    BINDINGS = [
        Binding("r", "refresh", "Rafraichir", show=True),
        Binding("escape", "app.pop_screen", "Retour", show=False),
    ]
    DEFAULT_CSS = """
    PartitionScreen { layout: vertical; }
    #part-header { height: auto; padding: 1 2; text-style: bold; }
    #part-status { padding: 0 2; height: 1; color: $text-muted; }
    #part-table-section { height: 1fr; margin: 0 1; border: solid $primary; padding: 0 1; }
    #command-log { height: 6; margin: 0 1; border: solid $primary-background; padding: 0 1; }
    #action-buttons { height: 3; padding: 0 2; layout: horizontal; }
    #action-buttons Button { margin: 0 1; }
    """
    def __init__(self, **kw):
        super().__init__(**kw)
        self._partitions = []

    @property
    def bridge(self):
        return getattr(self.app, "bridge", None)

    def compose(self) -> ComposeResult:
        yield Static("Partitions", id="part-header")
        yield Static("Statut : chargement...", id="part-status")
        with Vertical(id="part-table-section"):
            yield Label("Partitions disponibles")
            yield DataTable(id="part-table")
        yield Log(id="command-log", highlight=True, auto_scroll=True)
        with Horizontal(id="action-buttons"):
            yield Button("Rafraichir", id="btn-refresh")

    def on_mount(self):
        from fsdeploy.lib.ui.bridge import SchedulerBridge
        self.bridge = SchedulerBridge.default()
        dt = self.query_one("#part-table", DataTable)
        dt.add_columns("Device", "Taille", "Type", "Label")
        dt.cursor_type = "row"
        self._refresh()

    def _refresh(self):
        if not self.bridge:
            return
        self.bridge.emit("partition.list", callback=self._on_list)

    def _on_list(self, ticket):
        if ticket.status == "completed" and isinstance(ticket.result, list):
            self._partitions = ticket.result
            self._safe(self._refresh_table)
            self._safe(lambda: self._status(f"{len(self._partitions)} partitions"))

    def _refresh_table(self):
        dt = self.query_one("#part-table", DataTable)
        dt.clear()
        for p in self._partitions:
            dt.add_row(
                p.get("device", "?"),
                p.get("size", "?"),
                p.get("type", "?"),
                p.get("label", "?"),
            )

    def on_button_pressed(self, e):
        bid = e.button.id or ""
        if bid == "btn-refresh":
            self._refresh()

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
            self.query_one("#part-status", Static).update(f"Statut : {t}")
        except Exception:
            pass

    def _safe(self, fn):
        try:
            self.app.call_from_thread(fn)
        except Exception:
            fn()
