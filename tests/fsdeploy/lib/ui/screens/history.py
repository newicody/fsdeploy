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

from fsdeploy.lib.scheduler.intentlog.log import intent_log


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
        self.refresh()

    def action_refresh(self) -> None:
        table = self.query_one("#table", DataTable)
        table.clear(columns=True)
        table.add_columns("Heure", "Catégorie", "Action", "Données")
        store = intent_log.store
        records = []
        if store is not None:
            # Si c'est un HuffmanStore (ou a un attribut events)
            if hasattr(store, "events"):
                records = store.events.last(100)
            elif hasattr(store, "last"):
                records = store.last(100)
            for rec in records:
                dt = datetime.fromtimestamp(rec.timestamp).strftime("%H:%M:%S")
                tokens = " ".join(rec.tokens[:3]) if hasattr(rec, 'tokens') else ""
                category = getattr(rec, 'category', '')
                action = getattr(rec, 'action', '')
                table.add_row(dt, category, action, tokens)
        else:
            # Données fictives pour démonstration
            for i in range(5):
                ts = time.time() - i*10
                dt = datetime.fromtimestamp(ts).strftime("%H:%M:%S")
                table.add_row(dt, "event", "test", f"token{i}")

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        # Option: afficher plus de détails
        self.app.bell()
