"""
fsdeploy.ui.screens.zfs — Gestion des datasets ZFS, 100% bus events.
"""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Input, Label, Log, Static

class ZfsScreen(Screen):
    BINDINGS = [
        Binding("r", "refresh", "Rafraichir", show=True),
        Binding("c", "create_dataset", "Creer dataset", show=True),
        Binding("escape", "app.pop_screen", "Retour", show=False),
    ]
    DEFAULT_CSS = """
    ZfsScreen { layout: vertical; }
    #zfs-header { height: auto; padding: 1 2; text-style: bold; }
    #zfs-status { padding: 0 2; height: 1; color: $text-muted; }
    #zfs-table-section { height: 1fr; margin: 0 1; border: solid $primary; padding: 0 1; }
    #create-row { height: 3; padding: 0 2; layout: horizontal; }
    #create-row Input { width: 1fr; margin: 0 1; }
    #create-row Button { margin: 0 1; }
    #command-log { height: 6; margin: 0 1; border: solid $primary-background; padding: 0 1; }
    #action-buttons { height: 3; padding: 0 2; layout: horizontal; }
    #action-buttons Button { margin: 0 1; }
    """
    def __init__(self, **kw):
        super().__init__(**kw)
        self._datasets = []

    @property
    def bridge(self):
        return getattr(self.app, "bridge", None)

    def compose(self) -> ComposeResult:
        yield Static("Datasets ZFS", id="zfs-header")
        yield Static("Statut : chargement...", id="zfs-status")
        with Vertical(id="zfs-table-section"):
            yield Label("Datasets")
            yield DataTable(id="zfs-table")
        with Horizontal(id="create-row"):
            yield Label("Nom :")
            yield Input(placeholder="pool/dataset", id="input-dataset-name")
            yield Button("Creer", variant="primary", id="btn-create")
        yield Log(id="command-log", highlight=True, auto_scroll=True)
        with Horizontal(id="action-buttons"):
            yield Button("Rafraichir", id="btn-refresh")

    def on_mount(self):
        from fsdeploy.lib.ui.bridge import SchedulerBridge
        self.bridge = SchedulerBridge.default()
        dt = self.query_one("#zfs-table", DataTable)
        dt.add_columns("Dataset", "Utilise", "Disponible", "Mountpoint")
        dt.cursor_type = "row"
        self._refresh()

    def _refresh(self):
        if not self.bridge:
            return
        self.bridge.emit("dataset.list", pool="", callback=self._on_list)

    def _on_list(self, ticket):
        if ticket.status == "completed" and isinstance(ticket.result, list):
            self._datasets = ticket.result
            self._safe(self._refresh_table)
            self._safe(lambda: self._status(f"{len(self._datasets)} datasets"))

    def _refresh_table(self):
        dt = self.query_one("#zfs-table", DataTable)
        dt.clear()
        for d in self._datasets:
            dt.add_row(
                d.get("name", "?"),
                d.get("used", "?"),
                d.get("avail", "?"),
                d.get("mountpoint", "?"),
            )

    def on_button_pressed(self, e):
        bid = e.button.id or ""
        if bid == "btn-refresh":
            self._refresh()
        elif bid == "btn-create":
            self.action_create_dataset()

    def action_create_dataset(self):
        if not self.bridge:
            return
        name = self.query_one("#input-dataset-name", Input).value.strip()
        if not name:
            self.notify("Nom du dataset requis", severity="warning")
            return
        self.bridge.emit("dataset.create", name=name, callback=self._on_create_done)
        self._log(f"-> dataset.create({name})")

    def _on_create_done(self, ticket):
        if ticket.status == "completed":
            self._slog("Dataset créé")
            self._safe(self._refresh)
        else:
            self._slog(f"Erreur création : {ticket.error}")

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
            self.query_one("#zfs-status", Static).update(f"Statut : {t}")
        except Exception:
            pass

    def _safe(self, fn):
        try:
            self.app.call_from_thread(fn)
        except Exception:
            fn()
