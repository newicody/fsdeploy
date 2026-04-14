"""Module registry screen."""
from textual.screen import Screen
from fsdeploy.lib.modules.registry import ModuleRegistry

class ModuleRegistryScreen(Screen):
    """Screen that displays the module registry."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Utiliser la configuration passée à l'application
        self.registry = ModuleRegistry(self.app.config)

    def compose(self):
        # À implémenter plus tard
        from textual.widgets import Label
        yield Label("Module registry screen (TODO)")

__all__ = ["ModuleRegistryScreen"]
