"""
Écran Graph : visualisation des relations entre tâches et ressources.
"""

from textual.screen import Screen
from textual.widgets import Header, Footer, Static, Label, DataTable
from textual.binding import Binding
from textual.containers import Vertical


class GraphScreen(Screen):
    """
    Graphe des dépendances et des états du scheduler.
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
        Binding("a", "auto_layout", "Auto layout", show=True),
    ]

    DEFAULT_CSS = """
    GraphScreen {
        layout: vertical;
    }
    #graph-title {
        text-align: center;
        width: 100%;
        padding: 1 0;
        color: $accent;
        text-style: bold;
    }
    """

    def compose(self):
        yield Header()
        yield Static("Graph", id="graph-title")
        with Vertical():
            yield Label("Graphe interactif des tâches et intents.")
            yield Label("La visualisation sera bientôt disponible.")
            table = DataTable()
            table.add_columns("Noeud", "Type", "État")
            table.add_row("pool.boot", "pool", "actif")
            table.add_row("dataset.home", "dataset", "monté")
            yield table
        yield Footer()

    def action_refresh(self):
        """Rafraîchir le graphe."""
        self.notify("Rafraîchissement du graphe...", timeout=2)

    def action_auto_layout(self):
        """Applique un arrangement automatique des nœuds."""
        self.notify("Mise en page automatique appliquée.", timeout=2)
