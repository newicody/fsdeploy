"""
Écran de journal des erreurs pour afficher les échecs d'intents.
"""

from datetime import datetime
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, DataTable, Label
from textual.containers import Container, VerticalScroll


class ErrorLogScreen(Screen):
    """
    Affiche la liste des intents qui ont échoué.
    """

    BINDINGS = [("escape", "app.pop_screen", "Retour")]

    DEFAULT_CSS = """
    ErrorLogScreen {
        layout: vertical;
    }

    #error-title {
        height: auto;
        padding: 1 2;
        text-style: bold;
        background: $boost;
    }

    #error-table {
        height: 1fr;
        border: solid $accent;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        yield VerticalScroll(
            Label("Journal des erreurs (intents échoués)", id="error-title"),
            DataTable(id="error-table"),
        )
        yield Footer()

    def on_mount(self) -> None:
        self.refresh()

    @property
    def store(self):
        return getattr(self.app, "store", None)

    def refresh(self) -> None:
        table = self.query_one("#error-table", DataTable)
        table.clear()
        table.add_columns("Heure", "Catégorie", "Sévérité", "Message")
        if self.store is not None:
            try:
                # Utilisation de by_severity du HuffmanStore
                records = self.store.by_severity('error', limit=100)
            except AttributeError:
                records = []
        else:
            records = []
        for rec in records:
            ts = rec.timestamp
            dt = ""
            if ts:
                try:
                    dt = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
                except (ValueError, OSError):
                    dt = str(ts)
            category = getattr(rec, 'category', '')
            severity = getattr(rec, 'severity', '')
            # Utiliser les tokens comme message
            tokens = getattr(rec, 'tokens', [])
            msg = " ".join(tokens[:3]) if tokens else ""
            table.add_row(dt, category, severity, msg[:80])
        if not records:
            # Données fictives
            table.add_row("2026-01-01 12:00:00", "intent", "error", "Erreur de test")

    def action_app_pop_screen(self) -> None:
        self.app.pop_screen()
