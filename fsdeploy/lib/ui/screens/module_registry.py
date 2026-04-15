"""Module registry screen."""
from textual.screen import Screen
from fsdeploy.lib.modules.registry import ModuleRegistry

class ModuleRegistryScreen(Screen):
    """Screen that displays the module registry."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.registry = None

    def on_mount(self) -> None:
        """Initialize registry after the screen is attached to the app."""
        if hasattr(self.app, 'config') and self.app.config:
            from fsdeploy.lib.modules.registry import ModuleRegistry
            self.registry = ModuleRegistry(self.app.config)

    def compose(self):
        # À implémenter plus tard
        from textual.widgets import Label
        yield Label("Module registry screen (TODO)")

    @property
    def bridge(self):
        """Return the application's bridge instance."""
        return self.app.bridge

    def load_modules(self) -> None:
        """Load modules via the bridge."""
        if hasattr(self.app, 'bridge'):
            # Example: emit an event to load modules
            self.app.bridge.emit("module_registry.load")
            # update UI placeholder
            pass
        else:
            # Bridge not available
            pass

__all__ = ["ModuleRegistryScreen"]
