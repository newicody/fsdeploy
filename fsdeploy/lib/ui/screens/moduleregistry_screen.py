"""
Écran pour le registre de modules tiers.
"""

from textual.app import ComposeResult
from textual.containers import Container, Vertical, Horizontal
from textual.widgets import Header, Footer, Button, Input, Select, DataTable, Static, Label
from textual.widgets.data_table import RowSelected
from textual.screen import Screen
from textual.reactive import reactive
from textual import work

class ModuleRegistryScreen(Screen):
    """Permettre l'installation, la mise à jour et la suppression de modules tiers."""

    CSS = """
    ModuleRegistryScreen {
        layout: vertical;
    }
    .controls {
        height: 30%;
        padding: 1;
        border: solid $primary;
    }
    .modules {
        height: 70%;
        border: solid $secondary;
    }
    """

    bridge = SchedulerBridge.default()
    selected_module = reactive("")

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(classes="controls"):
            yield Static("Nom du module:")
            yield Input(placeholder="module‑zfs‑extra", id="module-name")
            yield Static("Version (optionnel):")
            yield Input(placeholder="1.0.0", id="module-version")
            yield Button("Installer", id="install")
            yield Button("Mettre à jour", id="update")
            yield Button("Supprimer", id="delete", variant="error")
        with Container(classes="modules"):
            yield DataTable(id="modules-table")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#modules-table", DataTable)
        table.add_columns("Nom", "Version", "Statut")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "install":
            self.install_module()
        elif event.button.id == "update":
            self.update_module()
        elif event.button.id == "delete":
            self.delete_module()

    def install_module(self):
        name_input = self.query_one("#module-name", Input)
        version_input = self.query_one("#module-version", Input)
        name = name_input.value
        version = version_input.value if version_input.value else ""
        params = {"name": name}
        if version:
            params["version"] = version
        ticket = self.bridge.emit("moduleregistry.install", params, callback=self.on_install_result)

    def update_module(self):
        name_input = self.query_one("#module-name", Input)
        name = name_input.value
        ticket = self.bridge.emit("moduleregistry.update", {"name": name}, callback=self.on_update_result)

    def delete_module(self):
        name_input = self.query_one("#module-name", Input)
        name = name_input.value
        ticket = self.bridge.emit("moduleregistry.delete", {"name": name}, callback=self.on_delete_result)

    def on_install_result(self, result):
        table = self.query_one("#modules-table", DataTable)
        if result and result.get("success"):
            module = result.get("module", {})
            table.add_row(module.get("name"), module.get("version"), "Installé")
        else:
            table.add_row("Erreur", "", "Échec")

    def on_update_result(self, result):
        # Similaire
        pass

    def on_delete_result(self, result):
        # Similaire
        pass
