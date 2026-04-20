"""
Écran IntentLog : consultation du journal des intents (HuffmanStore).
"""

import datetime
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, Label, DataTable
from textual.binding import Binding
from textual.containers import Vertical
from fsdeploy.lib.ui.bridge import SchedulerBridge


class IntentLogScreen(Screen):
    """
    Affiche le journal des intents (HuffmanStore).
    """
    @property
    def bridge(self):
        return self.app.bridge

    @property
    def config(self):
        return self.app.config

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
    #intentlog-table {
        height: 1fr;
        border: solid $primary;
        margin: 0 1;
        padding: 0 1;
    }
    """

    def compose(self):
        yield Header()
        yield Static("IntentLog", id="intentlog-title")
        with Vertical():
            yield Label("Journal des intents (dernières entrées) :")
            table = DataTable(id="intentlog-table")
            table.add_columns("Timestamp", "Catégorie", "Sévérité", "Message")
            yield table
        yield Footer()

    def on_mount(self) -> None:
        self.bridge = SchedulerBridge.default()
        self.refresh_logs()

    def refresh_logs(self):
        """Récupère les derniers enregistrements depuis le store."""
        table = self.query_one("#intentlog-table", DataTable)
        table.clear()

        # Accéder au store via l'application principale
        store = getattr(self.app, "store", None)
        if store is None:
            table.add_row("N/A", "store", "error", "Store non disponible")
            return

        try:
            # Obtenir les derniers enregistrements
            records = store.last(20)  # dernière vingtaine
            for rec in records:
                # Formater le timestamp
                ts = datetime.datetime.fromtimestamp(rec.timestamp).strftime("%Y-%m-%d %H:%M:%S")
                # Extraire le message (premier token du chemin)
                msg = rec.path.split('.')[-1] if rec.path else ""
                # Catégorie et sévérité
                cat = rec.category or "unknown"
                sev = rec.severity or "info"
                table.add_row(ts, cat, sev, msg)
        except Exception as e:
            table.add_row("N/A", "error", "error", f"Erreur : {e}")

    def action_refresh(self):
        """Rafraîchir le journal."""
        self.refresh_logs()
        self.notify("Journal des intents rafraîchi.", timeout=2)

    def action_filter(self):
        """Appliquer un filtre (placeholder)."""
        self.notify("Fonction de filtrage bientôt disponible.", timeout=2)
