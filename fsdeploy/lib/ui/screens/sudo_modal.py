"""
fsdeploy.ui.screens.sudo_modal
===============================
Modal de saisie de mot de passe pour les actions protégées.
"""

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import Label, Input, Button, Static
from textual import events


class SudoModal(ModalScreen[str]):
    """
    Modal pour demander un mot de passe sudo.
    
    Args:
        section_id: ID de la section de configuration
        action: Description de l'action protégée
    """
    
    DEFAULT_CSS = """
    SudoModal {
        align: center middle;
    }
    
    #sudo-dialog {
        width: 60;
        height: auto;
        padding: 1 2;
        background: $surface;
        border: thick $primary;
    }
    
    #sudo-title {
        text-align: center;
        margin: 1 0;
        text-style: bold;
    }
    
    #sudo-description {
        margin: 0 0 1 0;
        padding: 1;
        background: $panel;
    }
    
    #sudo-input {
        margin: 1 0;
    }
    
    #sudo-buttons {
        align-horizontal: right;
        height: auto;
        margin-top: 1;
    }
    
    #sudo-error {
        color: $error;
        margin-top: 1;
        display: none;
    }
    """
    
    def __init__(self, section_id: str, action: str = "", **kwargs):
        super().__init__(**kwargs)
        self.section_id = section_id
        self.action = action or f"Exécution de {section_id}"
        self.password = ""
    
    def compose(self) -> ComposeResult:
        with Container(id="sudo-dialog"):
            yield Label("Authentification requise", id="sudo-title")
            
            with Static(id="sudo-description"):
                yield Label(f"Action: {self.action}")
                yield Label("Cette action nécessite des privilèges sudo.")
            
            yield Input(
                placeholder="Mot de passe sudo",
                password=True,
                id="sudo-input"
            )
            
            with Container(id="sudo-buttons"):
                yield Button("Annuler", variant="error", id="sudo-cancel")
                yield Button("Valider", variant="primary", id="sudo-submit")
            
            yield Label("Mot de passe incorrect", id="sudo-error")
    
    def on_mount(self) -> None:
        """Focus sur le champ de saisie."""
        self.query_one("#sudo-input").focus()
    
    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Soumission du formulaire."""
        if event.input.id == "sudo-input":
            self._submit_password(event.value)
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Gestion des boutons."""
        if event.button.id == "sudo-submit":
            password = self.query_one("#sudo-input").value
            self._submit_password(password)
        elif event.button.id == "sudo-cancel":
            self.dismiss(None)
    
    def _submit_password(self, password: str) -> None:
        """Soumet le mot de passe."""
        if not password:
            self.query_one("#sudo-error").update("Le mot de passe ne peut pas être vide")
            self.query_one("#sudo-error").display = True
            return
        
        # Pour l'instant, nous allons simplement retourner le mot de passe
        # Dans une implémentation réelle, nous pourrions le valider d'abord
        self.dismiss(password)
