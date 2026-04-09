"""
Écran Security : gestion de la sécurité et des permissions.
"""

from textual.screen import Screen
from textual.widgets import Header, Footer, Static, Label, DataTable
from textual.binding import Binding
from textual.containers import Vertical


class SecurityScreen(Screen):
    """
    Aperçu et configuration des paramètres de sécurité.
    """

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Retour", show=True),
        Binding("r", "refresh", "Rafraîchir", show=True),
    ]

    DEFAULT_CSS = """
    SecurityScreen {
        layout: vertical;
    }
    #security-title {
        text-align: center;
        width: 100%;
        padding: 1 0;
        color: $accent;
        text-style: bold;
    }
    """

    def compose(self):
        yield Header()
        yield Static("Security", id="security-title")
        with Vertical():
            yield Label("Règles de sécurité et décorateurs.")
            table = DataTable()
            table.add_columns("Type", "Chemin", "Valeur")
            table.add_row("règle", "security.dataset.mount", "allow")
            table.add_row("règle", "security.dataset.snapshot", "deny")
            table.add_row("décorateur", "@security.kernel.compile", "active")
            yield table
        yield Footer()

    def action_refresh(self):
        """Rafraîchir les informations de sécurité."""
        self.notify("Mise à jour de la sécurité...", timeout=2)
