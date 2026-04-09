"""
Écran pour la gestion des noyaux multi‑architectures.
"""

from textual.app import ComposeResult
from textual.containers import Container, Vertical, Horizontal
from textual.widgets import Header, Footer, Button, Input, Select, DataTable, Static, Label
from textual.widgets.data_table import RowSelected
from textual.screen import Screen
from textual.reactive import reactive
from textual import work
from fsdeploy.lib.scheduler.bridge import SchedulerBridge

class MultiArchScreen(Screen):
    """Gérer les noyaux et initramfs pour différentes architectures."""

    CSS = """
    MultiArchScreen {
        layout: vertical;
    }
    .controls {
        height: 30%;
        padding: 1;
        border: solid $primary;
    }
    .results {
        height: 70%;
        border: solid $secondary;
    }
    """

    bridge = SchedulerBridge.default()
    selected_arch = reactive("")

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(classes="controls"):
            yield Static("Architecture:")
            yield Select([("aarch64", "aarch64"), ("riscv64", "riscv64"), ("x86_64", "x86_64")], id="arch")
            yield Static("Registre (optionnel):")
            yield Input(placeholder="registry.local", id="registry")
            yield Button("Synchroniser", id="sync")
            yield Button("Lister les noyaux", id="list")
        with Container(classes="results"):
            yield DataTable(id="kernels-table")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#kernels-table", DataTable)
        table.add_columns("Architecture", "Version", "Chemin")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "sync":
            self.sync_kernels()
        elif event.button.id == "list":
            self.list_kernels()

    def sync_kernels(self):
        arch_select = self.query_one("#arch", Select)
        registry_input = self.query_one("#registry", Input)
        arch = arch_select.value
        registry = registry_input.value if registry_input.value else ""
        params = {"arch": arch}
        if registry:
            params["registry"] = registry
        ticket = self.bridge.emit("multiarch.sync", params, callback=self.on_sync_result)

    def list_kernels(self):
        arch_select = self.query_one("#arch", Select)
        arch = arch_select.value
        ticket = self.bridge.emit("multiarch.list", {"arch": arch}, callback=self.on_list_result)

    def on_sync_result(self, result):
        table = self.query_one("#kernels-table", DataTable)
        if result and result.get("success"):
            kernels = result.get("kernels", [])
            table.clear()
            for k in kernels:
                table.add_row(k.get("arch"), k.get("version"), k.get("path"))
        else:
            table.clear()
            table.add_row("Erreur", "", "")

    def on_list_result(self, result):
        table = self.query_one("#kernels-table", DataTable)
        if result and result.get("success"):
            kernels = result.get("kernels", [])
            table.clear()
            for k in kernels:
                table.add_row(k.get("arch"), k.get("version"), k.get("path"))
        else:
            table.clear()
            table.add_row("Erreur", "", "")
