"""
fsdeploy.ui.screens.history — Historical log viewer.
Compatible : Textual >=8.2.1 / Rich >=14.3.3
"""
import time
from datetime import datetime
from typing import Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Label
from textual.containers import Vertical


class HistoryScreen(Screen):
    BINDINGS = [
        Binding("g", "app.pop_screen", "Fermer", show=True),
        Binding("escape", "app.pop_screen", "Retour", show=False),
        Binding("r", "refresh", "Actualiser", show=True),
    ]
    DEFAULT_CSS = """
    HistoryScreen { layout: vertical; }
    #title { height: auto; padding: 1 2; text-style: bold; background: $boost; }
    #table { height: 1fr; }
    """

    def compose(self) -> ComposeResult:
        yield Label("Historique des logs (100 derniers événements)", id="title")
        yield DataTable(id="table")
        yield Footer()

    def on_mount(self) -> None:
        from fsdeploy.lib.ui.bridge import SchedulerBridge
        self.bridge = SchedulerBridge.default()
        self.refresh()

    @property
    def store(self):
        return getattr(self.app, "store", None)

    def action_refresh(self) -> None:
        table = self.query_one("#table", DataTable)
        table.clear(columns=True)
        table.add_columns("Heure", "Catégorie", "Action", "Données")
        if self.store is not None:
            try:
                # Utilisation de la méthode last du HuffmanStore
                records = self.store.last(100)
            except AttributeError:
                records = []
        else:
            records = []
        for rec in records:
            dt = datetime.fromtimestamp(rec.timestamp).strftime("%H:%M:%S")
            tokens = " ".join(rec.tokens[:3]) if hasattr(rec, 'tokens') else ""
            category = getattr(rec, 'category', '')
            action = getattr(rec, 'action', '')
            table.add_row(dt, category, action, tokens)
        if not records:
            # Données fictives pour démonstration
            for i in range(5):
                ts = time.time() - i*10
                dt = datetime.fromtimestamp(ts).strftime("%H:%M:%S")
                table.add_row(dt, "event", "test", f"token{i}")

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        # Option: afficher plus de détails
        self.app.bell()
