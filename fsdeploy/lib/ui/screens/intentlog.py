"""
Écran IntentLog : consultation du journal des intents.
"""

from textual.screen import Screen
from textual.widgets import Header, Footer, Static, Label, DataTable
from textual.binding import Binding
from textual.containers import Vertical


class IntentLogScreen(Screen):
    """
    Affiche le journal des intents (HuffmanStore).
    """

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Retour", show=True),
        Binding("r", "refresh", "Rafraîchir", show=True),
        Binding("f", "filter", "Filtrer", show=True),
    ]

    DEFAULT_CSS = """
    IntentLogScreen {
        layout: vertical;
    }
    #intentlog-title {
        text-align: center;
        width: 100%;
        padding: 1 0;
        color: $accent;
        text-style: bold;
    }
    """

    def compose(self):
        yield Header()
        yield Static("IntentLog", id="intentlog-title")
        with Vertical():
            yield Label("Journal des intents (dernières entrées) :")
            table = DataTable()
            table.add_columns("Timestamp", "Catégorie", "Sévérité", "Message")
            table.add_row("2026-04-08 10:00", "task", "info", "Détection terminée")
            table.add_row("2026-04-08 09:58", "event", "warning", "Pool absent")
            table.add_row("2026-04-08 09:55", "intent", "error", "Échec du montage")
            yield table
        yield Footer()

    def action_refresh(self):
        """Rafraîchir le journal."""
        self.notify("Journal des intents rafraîchi.", timeout=2)

    def action_filter(self):
        """Appliquer un filtre."""
        self.notify("Fonction de filtrage bientôt disponible.", timeout=2)
