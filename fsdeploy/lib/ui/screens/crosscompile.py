"""
fsdeploy.ui.screens.crosscompile — Cross‑compilation kernel.
"""
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, Label, DataTable
from textual.binding import Binding
from textual.containers import Vertical


class CrossCompileScreen(Screen):
    """
    Cross‑compilation screen for building kernels for other architectures.
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
    CrossCompileScreen {
        layout: vertical;
    }
    #crosscompile-title {
        text-align: center;
        width: 100%;
        padding: 1 0;
        color: $accent;
        text-style: bold;
    }
    """

    def compose(self):
        yield Header()
        yield Static("Cross‑compilation", id="crosscompile-title")
        with Vertical():
            yield Label("Cross‑compilation kernel.")
            table = DataTable()
            table.add_columns("Architecture", "Toolchain", "Statut")
            table.add_row("aarch64", "gcc-aarch64-linux-gnu", "disponible")
            table.add_row("riscv64", "gcc-riscv64-linux-gnu", "manquant")
            yield table
        yield Footer()

    def action_refresh(self):
        """Refresh cross‑compilation status."""
        self.notify("Mise à jour des toolchains...", timeout=2)
