"""
fsdeploy.ui.screens.multiarch — Multi‑architecture support.
"""
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, Label, DataTable
from textual.binding import Binding
from textual.containers import Vertical


class MultiArchScreen(Screen):
    """
    Multi‑architecture support screen.
    """

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Retour", show=True),
        Binding("r", "refresh", "Rafraîchir", show=True),
    ]

    @property
    def bridge(self):
        return self.app.bridge

    @property
    def config(self):
        return self.app.config

    DEFAULT_CSS = """
    MultiArchScreen {
        layout: vertical;
    }
    #multiarch-title {
        text-align: center;
        width: 100%;
        padding: 1 0;
        color: $accent;
        text-style: bold;
    }
    """

    def compose(self):
        yield Header()
        yield Static("Multi‑architecture", id="multiarch-title")
        with Vertical():
            yield Label("Gestion des architectures multiples.")
            table = DataTable()
            table.add_columns("Architecture", "Kernel", "Initramfs", "Boot")
            table.add_row("amd64", "6.12.0", "dracut", "UEFI")
            table.add_row("arm64", "6.10.0", "dracut", "U‑boot")
            yield table
        yield Footer()

    def action_refresh(self):
        """Refresh multi‑architecture status."""
        self.notify("Mise à jour des architectures...", timeout=2)
