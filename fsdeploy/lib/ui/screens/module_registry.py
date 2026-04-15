"""
Module registry screen.

Displays loaded modules and their status, allowing the user to enable/disable
modules and configure their options.
"""

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, DataTable

class ModuleRegistryScreen(Screen):
    """
    Screen for managing fsdeploy modules.
    """

    BINDINGS = [("escape", "app.pop_screen", "Back")]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.registry = None

    def on_mount(self) -> None:
        """Initialize registry after the screen is attached to the app."""
        if hasattr(self.app, 'config') and self.app.config:
            from fsdeploy.lib.modules.registry import ModuleRegistry
            self.registry = ModuleRegistry(self.app.config)
        self.populate_table()

    def populate_table(self) -> None:
        """Fill the data table with module information."""
        table = self.query_one("#module_table", DataTable)
        table.clear()
        table.add_columns("Module", "Status", "Description")
        # Example data; in a real implementation we would query self.config
        # and self.bridge for actual module information.
        if self.config:
            # Access config to demonstrate validation
            # (no‑op, just to show that self.app.config is usable)
            pass
        table.add_rows([
            ("zfs", "enabled", "ZFS integration"),
            ("kernel", "enabled", "Kernel management"),
            ("init", "disabled", "Init system integration"),
        ])

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Header()
        yield Container(
            Static("Module Registry", classes="title"),
            Static("This screen shows all loaded modules.", classes="subtitle"),
            DataTable(id="module_table"),
            classes="center"
        )
        yield Footer()

    @property
    def bridge(self):
        """Bridge to the scheduler."""
        return self.app.bridge

    @property
    def config(self):
        """FsDeployConfig instance."""
        return self.app.config

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
