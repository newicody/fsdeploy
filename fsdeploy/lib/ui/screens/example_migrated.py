"""
Exemple d'écran migré sans subprocess.
"""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Button, Log, Static
from textual.containers import Container

from fsdeploy.lib.ui.events import LogMessage
from fsdeploy.lib.ui.bridge import SchedulerBridge

class ExampleMigratedScreen(Screen):
    """Exemple d'écran complètement migré."""
    
    DEFAULT_CSS = """
    ExampleMigratedScreen {
        layout: vertical;
    }
    
    #header {
        padding: 1 2;
        text-style: bold;
    }
    
    #log {
        height: 1fr;
        border: solid $primary;
        padding: 0 1;
    }
    
    #buttons {
        height: 3;
        padding: 0 2;
        layout: horizontal;
    }
    """
    
    def compose(self) -> ComposeResult:
        yield Static("Exemple d'écran migré", id="header")
        yield Log(id="log")
        with Container(id="buttons"):
            yield Button("Tester commande simple", id="btn-simple")
            yield Button("Tester commande avec sudo", id="btn-sudo", variant="warning")
    
    def on_mount(self) -> None:
        self.bridge = SchedulerBridge.default()
        self.current_ticket_id = None
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-simple":
            self._test_simple_command()
        elif event.button.id == "btn-sudo":
            self._test_sudo_command()
    
    def _test_simple_command(self) -> None:
        """Test d'une commande simple via bridge."""
        self.current_ticket_id = self.bridge.emit(
            "example.simple",
            message="Test de commande simple",
            callback=self._on_simple_done
        )
        self._log("Commande simple envoyée...")
    
    def _on_simple_done(self, ticket) -> None:
        if ticket.status == "completed":
            self._log(f"✅ Succès: {ticket.result}")
        else:
            self._log(f"❌ Erreur: {ticket.error}")
    
    def _test_sudo_command(self) -> None:
        """Test d'une commande nécessitant sudo."""
        self.current_ticket_id = self.bridge.emit(
            "example.sudo",
            action="Test de commande sudo",
            callback=self._on_sudo_done
        )
        self._log("Commande sudo envoyée...")
    
    def _on_sudo_done(self, ticket) -> None:
        if ticket.status == "completed":
            self._log("✅ Commande sudo exécutée avec succès")
        else:
            self._log(f"❌ Erreur sudo: {ticket.error}")
    
    def on_log_message(self, event: LogMessage) -> None:
        """Capture les messages de log du scheduler."""
        # Afficher tous les logs ou filtrer par ticket_id
        prefix = ""
        if event.level == "error":
            prefix = "[red]❌[/] "
        elif event.level == "success":
            prefix = "[green]✅[/] "
        elif event.level == "warning":
            prefix = "[yellow]⚠️[/] "
        
        self._log(f"{prefix}{event.log}")
    
    def _log(self, message: str) -> None:
        """Ajoute un message au log."""
        self.query_one("#log", Log).write_line(message)
