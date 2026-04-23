"""
fsdeploy.ui.screens.ZfsPoolScreen
==================================
Écran de création de pool ZFS.

Avant la migration (add.md 24.1) :
  - Utilisait subprocess pour exécuter zpool create
  - Gestion manuelle des erreurs et de la sortie console

Après la migration (add.md 38.5) :
  - Collecte uniquement les données du formulaire
  - Émet une intention ZFS_POOL_CREATE via le bridge
  - Reçoit les logs en temps réel via TASK_LOG
"""

import subprocess  # À SUPPRIMER
import os          # À SUPPRIMER
from typing import Optional, List

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import (
    Header, Footer, RichLog, Button, Input, 
    Select, Static, Label, LoadingIndicator
)
from textual.containers import Container, Horizontal, Vertical
from textual.message import Message
from textual.reactive import reactive

from fsdeploy.lib.ui.events import LogMessage, TaskStatusMessage


class ZfsPoolScreen(Screen):
    """Écran de création de pool ZFS via intentions."""
    
    CSS = """
    #log_widget {
        height: 12;
        border: solid $accent;
        padding: 0 1;
    }
    
    .form-section {
        padding: 1;
        border: solid $primary-background;
        margin: 1 0;
    }
    
    #create_button {
        margin: 1 0;
    }
    
    #status_indicator {
        margin-left: 1;
    }
    """
    
    # Données du formulaire
    pool_name = reactive("")
    selected_disks = reactive([])
    pool_options = reactive({})
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ticket_id: Optional[str] = None
        self.log_widget: Optional[RichLog] = None
        
    def compose(self) -> ComposeResult:
        yield Header()
        
        with Container(id="main_container"):
            # Section formulaire
            with Vertical(classes="form-section"):
                yield Label("Création de pool ZFS", classes="section-title")
                yield Input(placeholder="Nom du pool", id="pool_name_input")
                
                # Sélection des disques (simplifiée)
                yield Label("Disques disponibles:")
                yield Select(
                    [(f"/dev/sd{x}", f"/dev/sd{x}") for x in ['a', 'b', 'c', 'd']],
                    id="disks_select",
                    multiple=True
                )
                
                # Options du pool
                yield Label("Options du pool:")
                yield Input(
                    placeholder="Compression=on,ashift=12",
                    id="options_input"
                )
                
                with Horizontal():
                    yield Button("Créer le pool", variant="primary", id="create_button")
                    yield LoadingIndicator(id="status_indicator", visible=False)
            
            # Widget de logs en temps réel
            yield Label("Logs d'exécution:", classes="section-title")
            yield RichLog(id="log_widget", highlight=True, markup=True)
        
        yield Footer()
    
    def on_mount(self) -> None:
        """Initialisation après le montage de l'écran."""
        self.log_widget = self.query_one("#log_widget", RichLog)
        self.log_widget.write("[INFO] Écran ZFS Pool prêt. Remplissez le formulaire.")
        
        # S'abonner aux événements de log
        # Note: Dans Textual, on utilise watch ou on_message
        # Pour les logs du scheduler, on utilisera on_log_message
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Gestion des clics sur les boutons."""
        if event.button.id == "create_button":
            self.create_pool()
    
    def on_input_changed(self, event: Input.Changed) -> None:
        """Mise à jour des données réactives."""
        if event.input.id == "pool_name_input":
            self.pool_name = event.value
        elif event.input.id == "options_input":
            # Parser les options (simplifié)
            options = {}
            if event.value:
                for opt in event.value.split(','):
                    if '=' in opt:
                        k, v = opt.split('=', 1)
                        options[k.strip()] = v.strip()
            self.pool_options = options
    
    def on_select_changed(self, event: Select.Changed) -> None:
        """Mise à jour des disques sélectionnés."""
        if event.select.id == "disks_select":
            self.selected_disks = list(event.value)
    
    def create_pool(self) -> None:
        """Collecte les données et émet l'intention de création de pool."""
        # Validation basique
        if not self.pool_name:
            self.log_widget.write("[ERREUR] Le nom du pool est requis.")
            return
        
        if not self.selected_disks:
            self.log_widget.write("[ERREUR] Sélectionnez au moins un disque.")
            return
        
        # Préparer les données
        pool_data = {
            "pool_name": self.pool_name,
            "disks": self.selected_disks,
            "options": self.pool_options,
            "force": False,  # Option de sécurité
        }
        
        self.log_widget.write(f"[INFO] Émission de l'intention ZFS_POOL_CREATE...")
        self.log_widget.write(f"[DEBUG] Données: {pool_data}")
        
        # Afficher l'indicateur de chargement
        status_indicator = self.query_one("#status_indicator", LoadingIndicator)
        status_indicator.visible = True
        
        # ANCIEN CODE À SUPPRIMER (exemple):
        # try:
        #     cmd = ["zpool", "create", self.pool_name] + self.selected_disks
        #     result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        #     self.log_widget.write(f"[SUCCÈS] Pool créé: {result.stdout}")
        # except subprocess.CalledProcessError as e:
        #     self.log_widget.write(f"[ERREUR] Échec: {e.stderr}")
        
        # NOUVEAU CODE selon add.md 38.5:
        # Émettre l'intention via le bridge
        if hasattr(self.app, 'bridge'):
            self.ticket_id = self.app.bridge.emit(
                "EXECUTE_INTENT",
                {
                    "id": "ZFS_POOL_CREATE",
                    "params": pool_data
                },
                callback=self.on_pool_creation_result
            )
            self.log_widget.write(f"[INFO] Ticket créé: {self.ticket_id}")
        else:
            self.log_widget.write("[ERREUR] Bridge non disponible.")
            status_indicator.visible = False
    
    def on_pool_creation_result(self, ticket) -> None:
        """Callback appelé lorsque l'intention est terminée."""
        status_indicator = self.query_one("#status_indicator", LoadingIndicator)
        status_indicator.visible = False
        
        if ticket.status == "completed":
            self.log_widget.write(f"[SUCCÈS] Pool créé avec succès!")
            self.log_widget.write(f"[INFO] Résultat: {ticket.result}")
        elif ticket.status == "failed":
            self.log_widget.write(f"[ERREUR] Échec de création: {ticket.error}")
    
    def on_log_message(self, event: LogMessage) -> None:
        """Reçoit les logs du scheduler en temps réel."""
        # Filtrer par ticket_id si nécessaire
        if self.ticket_id and event.ticket_id != self.ticket_id:
            return
        
        # Afficher le log dans le widget
        prefix = {
            "info": "[INFO]",
            "warning": "[WARN]",
            "error": "[ERREUR]",
            "success": "[SUCCÈS]"
        }.get(event.level, "[INFO]")
        
        self.log_widget.write(f"{prefix} {event.log}")
    
    def on_task_status_message(self, event: TaskStatusMessage) -> None:
        """Reçoit les mises à jour de statut des tâches."""
        # Mettre à jour l'UI en fonction du statut
        if event.status == "started":
            self.log_widget.write(f"[INFO] Tâche démarrée: {event.node_id}")
        elif event.status == "running":
            self.log_widget.write(f"[INFO] Progression: {event.progress*100:.1f}%")
        elif event.status == "completed":
            self.log_widget.write(f"[SUCCÈS] Tâche terminée: {event.node_id}")
        elif event.status == "failed":
            self.log_widget.write(f"[ERREUR] Tâche échouée: {event.node_id} - {event.message}")
