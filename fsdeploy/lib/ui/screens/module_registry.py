"""
Écran du registre des modules pour fsdeploy.

Permet de parcourir, installer et mettre à jour des modules tiers
depuis un registre distant.
"""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, DataTable, Label, Button
from textual.containers import Container, VerticalScroll, Horizontal
from textual.binding import Binding

from fsdeploy.lib.modules.registry import ModuleRegistry


class ModuleRegistryScreen(Screen):
    """
    Affiche la liste des modules disponibles dans le registre.
    """

    BINDINGS = [
        ("escape", "app.pop_screen", "Retour"),
        ("r", "refresh", "Rafraîchir"),
        ("i", "install", "Installer le module sélectionné"),
    ]

    DEFAULT_CSS = """
    ModuleRegistryScreen {
        layout: vertical;
    }

    #registry-title {
        height: auto;
        padding: 1 2;
        text-style: bold;
        background: $boost;
    }

    #module-table {
        height: 1fr;
        border: solid $accent;
    }

    #button-bar {
        height: auto;
        padding: 1 2;
        border-top: solid $panel;
    }
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.registry = ModuleRegistry()
        self.modules = []

    def compose(self) -> ComposeResult:
        yield Header()
        yield VerticalScroll(
            Label("Registre des modules tiers", id="registry-title"),
            DataTable(id="module-table"),
        )
        yield Horizontal(
            Button("Rafraîchir", variant="primary", id="refresh"),
            Button("Installer", variant="success", id="install"),
            Button("Retour", variant="default", id="back"),
            id="button-bar",
        )
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#module-table", DataTable)
        table.add_columns("Nom", "Version", "Description", "Statut")
        self.refresh_modules()

    def refresh_modules(self) -> None:
        """Met à jour la liste des modules depuis le registre."""
        self.modules = self.registry.list_remote()
        table = self.query_one("#module-table", DataTable)
        table.clear()
        for mod in self.modules:
            installed = self.registry.is_installed(mod["name"])
            status = "✅" if installed else "⭕"
            table.add_row(
                mod["name"],
                mod.get("version", "?"),
                mod.get("description", ""),
                status,
            )

    def action_refresh(self) -> None:
        self.refresh_modules()
        self.notify("Liste des modules rafraîchie", severity="information")

    def action_install(self) -> None:
        table = self.query_one("#module-table", DataTable)
        if not table.cursor_row:
            self.notify("Aucun module sélectionné", severity="warning")
            return
        row_index = table.cursor_row
        if row_index >= len(self.modules):
            return
        module = self.modules[row_index]
        name = module["name"]
        try:
            self.registry.install(name)
            self.notify(f"Module '{name}' installé avec succès", severity="success")
            self.refresh_modules()
        except Exception as e:
            self.notify(f"Échec d'installation : {e}", severity="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "refresh":
            self.action_refresh()
        elif event.button.id == "install":
            self.action_install()
        elif event.button.id == "back":
            self.app.pop_screen()
