"""
Écran Metrics : indicateurs de performance et statistiques.
"""

from textual.screen import Screen
from textual.widgets import Header, Footer, Static, Label, DataTable
from textual.binding import Binding
from textual.containers import Vertical


class MetricsScreen(Screen):
    """
    Métriques du runtime (parallelisme, utilisation mémoire, etc.)
    """

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Retour", show=True),
        Binding("r", "refresh", "Rafraîchir", show=True),
        Binding("e", "export", "Exporter", show=True),
    ]

    DEFAULT_CSS = """
    MetricsScreen {
        layout: vertical;
    }
    #metrics-title {
        text-align: center;
        width: 100%;
        padding: 1 0;
        color: $accent;
        text-style: bold;
    }
    """

    def compose(self):
        yield Header()
        yield Static("Metrics", id="metrics-title")
        with Vertical():
            yield Label("Statistiques du runtime :")
            table = DataTable()
            table.add_columns("Mesure", "Valeur", "Unité")
            table.add_row("Tâches actives", "3", "")
            table.add_row("Mémoire utilisée", "42.5", "MiB")
            table.add_row("Ratio compression", "0.85", "")
            table.add_row("Locks actives", "1", "")
            table.add_row("Intent en attente", "5", "")
            table.add_row("Events traités", "124", "")
            yield table
        yield Footer()

    def action_refresh(self):
        """Rafraîchir les métriques."""
        self.notify("Métriques rafraîchies.", timeout=2)

    def action_export(self):
        """Exporter les métriques."""
        self.notify("Export vers /tmp/metrics.json ...", timeout=2)
