"""
fsdeploy.ui.screens.format — Formatage des partitions, 100% bus events.
"""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Input, Label, Log, Select, Static

class FormatScreen(Screen):
    BINDINGS = [
        Binding("f", "format", "Formater", show=True),
        Binding("escape", "app.pop_screen", "Retour", show=False),
    ]
    DEFAULT_CSS = """
    FormatScreen { layout: vertical; }
    #fmt-header { height: auto; padding: 1 2; text-style: bold; }
    #fmt-status { padding: 0 2; height: 1; color: $text-muted; }
    #fmt-table-section { height: 1fr; margin: 0 1; border: solid $primary; padding: 0 1; }
    #fmt-options { height: auto; margin: 0 1; padding: 1 2; border: solid $accent; }
    .fmt-row { height: 3; layout: horizontal; }
    .fmt-row Label { width: 18; padding: 1 0; }
    .fmt-row Input, .fmt-row Select { width: 1fr; }
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
        yield Static("Formatage", id="fmt-header")
        yield Static("Statut : chargement...", id="fmt-status")
        with Vertical(id="fmt-table-section"):
            yield Label("Partitions disponibles")
            yield DataTable(id="fmt-table")
        with Vertical(id="fmt-options"):
            yield Label("Options de formatage")
            with Horizontal(classes="fmt-row"):
                yield Label("Filesystem :")
                yield Select([("ext4", "ext4"), ("xfs", "xfs"), ("btrfs", "btrfs")], value="ext4", id="select-fs")
            with Horizontal(classes="fmt-row"):
                yield Label("Label :")
                yield Input(placeholder="mon-label", id="input-label")
        yield Log(id="command-log", highlight=True, auto_scroll=True)
        with Horizontal(id="action-buttons"):
            yield Button("Formater", variant="primary", id="btn-format")
            yield Button("Rafraichir", id="btn-refresh")

    def on_mount(self):
        from fsdeploy.lib.ui.bridge import SchedulerBridge
        self.bridge = SchedulerBridge.default()
        dt = self.query_one("#fmt-table", DataTable)
        dt.add_columns("Device", "Taille", "Type")
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
        dt = self.query_one("#fmt-table", DataTable)
        dt.clear()
        for p in self._partitions:
            dt.add_row(
                p.get("device", "?"),
                p.get("size", "?"),
                p.get("type", "?"),
            )

    def on_button_pressed(self, e):
        bid = e.button.id or ""
        if bid == "btn-format":
            self.action_format()
        elif bid == "btn-refresh":
            self._refresh()

    def action_format(self):
        if not self.bridge:
            return
        table = self.query_one("#fmt-table", DataTable)
        idx = table.cursor_row
        if idx is None or idx >= len(self._partitions):
            self.notify("Selectionnez une partition", severity="warning")
            return
        device = self._partitions[idx].get("device", "")
        fs = self.query_one("#select-fs", Select).value
        label = self.query_one("#input-label", Input).value.strip()
        self.bridge.emit("partition.format", device=device, filesystem=fs, label=label,
                         callback=self._on_format_done)
        self._log(f"-> partition.format({device}, {fs})")

    def _on_format_done(self, ticket):
        if ticket.status == "completed":
            self._slog("Formatage terminé")
            self._safe(self._refresh)
        else:
            self._slog(f"Erreur formatage : {ticket.error}")

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
            self.query_one("#fmt-status", Static).update(f"Statut : {t}")
        except Exception:
            pass

    def _safe(self, fn):
        try:
            self.app.call_from_thread(fn)
        except Exception:
            fn()
