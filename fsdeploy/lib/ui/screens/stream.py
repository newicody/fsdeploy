"""
fsdeploy.ui.screens.stream
===========================
Écran de logs interactif utilisant les événements LogMessage du bridge.
Conforme à add.md §2.
"""
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import RichLog, Header, Footer
from fsdeploy.lib.ui.events import LogMessage


class StreamScreen(Screen):
    """Affiche les logs en continu via les événements LogMessage."""

    def compose(self) -> ComposeResult:
        yield Header()
        yield RichLog(id="log", highlight=True, markup=True, max_lines=500)
        yield Footer()

    def on_mount(self) -> None:
        self.log_widget = self.query_one("#log", RichLog)
        self.title = "Logs"

    def on_log_message(self, event: LogMessage) -> None:
        """Reçoit les logs du bridge via l'application."""
        style = {
            "error": "red",
            "warning": "yellow",
            "success": "green",
            "info": "white",
        }.get(event.level, "white")
        self.log_widget.write(f"[{style}]{event.log}[/]")
