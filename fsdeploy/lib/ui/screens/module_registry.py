"""
Écran du registre des modules (désactivé).
"""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, Label
from textual.containers import VerticalScroll


class ModuleRegistryScreen(Screen):
    """Stub écran du registre des modules."""

    BINDINGS = [("escape", "app.pop_screen", "Retour")]

    def compose(self) -> ComposeResult:
        yield Header()
        yield VerticalScroll(
            Label("Le registre des modules est désactivé dans cette version.", id="message"),
        )
        yield Footer()
