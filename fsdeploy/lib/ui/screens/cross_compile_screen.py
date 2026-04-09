"""
Écran pour la compilation croisée (aarch64, riscv64).
"""

from textual.app import ComposeResult
from textual.containers import Container, Vertical, Horizontal
from textual.widgets import Header, Footer, Button, Input, Select, DataTable, Static, Label
from textual.widgets.data_table import RowSelected
from textual.screen import Screen
from textual.reactive import reactive
from textual import work
from fsdeploy.lib.scheduler.bridge import SchedulerBridge

class CrossCompileScreen(Screen):
    """Lancer une compilation croisée et suivre la progression."""

    CSS = """
    CrossCompileScreen {
        layout: vertical;
    }
    .controls {
        height: 30%;
        padding: 1;
        border: solid $primary;
    }
    .logs {
        height: 70%;
        border: solid $secondary;
    }
    """

    bridge = SchedulerBridge.default()
    selected_arch = reactive("")

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(classes="controls"):
            yield Static("Architecture cible:")
            yield Select([("aarch64", "aarch64"), ("riscv64", "riscv64"), ("ppc64le", "ppc64le")], id="arch")
            yield Static("Version du noyau (optionnel):")
            yield Input(placeholder="6.6.47", id="kernel-ver")
            yield Button("Lancer la compilation", id="start")
            yield Button("Arrêter", id="stop", variant="error")
        with Container(classes="logs"):
            yield Static(id="compile-output")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#compile-output", Static).update("Prêt.")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "start":
            self.start_compile()
        elif event.button.id == "stop":
            self.stop_compile()

    def start_compile(self):
        arch_select = self.query_one("#arch", Select)
        kernel_input = self.query_one("#kernel-ver", Input)
        arch = arch_select.value
        kernel = kernel_input.value if kernel_input.value else ""
        params = {"arch": arch}
        if kernel:
            params["kernel"] = kernel
        ticket = self.bridge.emit("crosscompile.launch", params, callback=self.on_compile_result)

    def stop_compile(self):
        ticket = self.bridge.emit("crosscompile.stop", callback=self.on_stop_result)

    def on_compile_result(self, result):
        output = self.query_one("#compile-output", Static)
        if result and result.get("success"):
            output.update(f"Compilation lancée: {result.get('message', '')}")
        else:
            output.update("Échec du lancement.")

    def on_stop_result(self, result):
        output = self.query_one("#compile-output", Static)
        if result and result.get("success"):
            output.update("Compilation arrêtée.")
        else:
            output.update("Échec de l'arrêt.")
