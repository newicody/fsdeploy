"""
Écran de navigation principal permettant d'accéder à tous les écrans spécialisés.
"""

from textual.app import ComposeResult
from textual.containers import Container, Vertical, Horizontal
from textual.widgets import Header, Footer, Button, Static
from textual.screen import Screen

# Import des écrans spécialisés (certains sont des versions améliorées)
from fsdeploy.lib.ui.screens.graph_enhanced import GraphEnhancedScreen
from fsdeploy.lib.ui.screens.security_enhanced import SecurityEnhancedScreen
from fsdeploy.lib.ui.screens.partition_detection import PartitionDetectionScreen
from fsdeploy.lib.ui.screens.crosscompile import CrossCompileScreen
from fsdeploy.lib.ui.screens.multiarch import MultiArchScreen
from fsdeploy.lib.ui.screens.module_registry import ModuleRegistryScreen


class NavigationScreen(Screen):
    """Écran d'accueil avec liens vers tous les écrans spécialisés (versions améliorées)."""

    CSS = """
    NavigationScreen {
        layout: vertical;
    }
    .title {
        padding: 1;
        border: solid $primary;
        text-align: center;
    }
    .buttons {
        padding: 1;
        height: 80%;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(classes="title"):
            yield Static("📊 fsdeploy — Navigation principale", classes="title")
        with Container(classes="buttons"):
            yield Button("Graph animé des dépendances", id="graph", variant="primary")
            yield Button("Règles de sécurité", id="security")
            yield Button("Détection des partitions", id="partition")
            yield Button("Compilation croisée", id="crosscompile")
            yield Button("Noyaux multi‑architectures", id="multiarch")
            yield Button("Registre de modules", id="moduleregistry")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        screen_map = {
            "graph": GraphEnhancedScreen,
            "security": SecurityEnhancedScreen,
            "partition": PartitionDetectionScreen,
            "crosscompile": CrossCompileScreen,
            "multiarch": MultiArchScreen,
            "moduleregistry": ModuleRegistryScreen,
        }
        if button_id in screen_map:
            self.app.switch_screen(screen_map[button_id]())
