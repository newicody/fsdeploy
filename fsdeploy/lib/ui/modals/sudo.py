"""
Modal pour la saisie du mot de passe sudo.
"""

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static


class SudoModal(ModalScreen[str]):
    """Modal pour demander le mot de passe sudo."""
    
    DEFAULT_CSS = """
    SudoModal {
        align: center middle;
    }
    
    SudoModal > Container {
        width: 60;
        height: 16;
        padding: 1 2;
        background: $surface;
        border: thick $primary;
    }
    
    #sudo-title {
        text-align: center;
        text-style: bold;
        padding-bottom: 1;
    }
    
    #sudo-description {
        height: auto;
        padding: 1 0;
    }
    
    #sudo-input {
        width: 100%;
        margin: 1 0;
        password: true;
    }
    
    #sudo-buttons {
        height: auto;
        layout: horizontal;
        align: right middle;
        padding-top: 1;
    }
    
    #sudo-buttons Button {
        margin-left: 1;
    }
    """
    
    def __init__(self, task_description: str = "", **kwargs):
        super().__init__(**kwargs)
        self.task_description = task_description
        self.password = ""
    
    def compose(self) -> ComposeResult:
        with Container():
            yield Static("Authentification Sudo Requise", id="sudo-title")
            yield Label(f"La tâche suivante nécessite des privilèges administrateur:\n\n{self.task_description}", id="sudo-description")
            yield Input(placeholder="Mot de passe sudo", id="sudo-input", password=True)
            with Container(id="sudo-buttons"):
                yield Button("Annuler", variant="error", id="btn-cancel")
                yield Button("Valider", variant="primary", id="btn-submit")
    
    def on_mount(self) -> None:
        self.query_one("#sudo-input", Input).focus()
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.dismiss(None)
        elif event.button.id == "btn-submit":
            self.password = self.query_one("#sudo-input", Input).value
            self.dismiss(self.password)
    
    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "sudo-input":
            self.password = event.value
            self.dismiss(self.password)
