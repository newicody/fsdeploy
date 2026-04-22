"""
fsdeploy.ui.events
====================
Événements Textual personnalisés pour fsdeploy.
"""

from textual.message import Message


class LogMessage(Message):
    """Message pour les logs du scheduler."""
    
    def __init__(self, log: str, stream: str = "stdout", 
                 ticket_id: str = None, level: str = "info") -> None:
        self.log = log
        self.stream = stream
        self.ticket_id = ticket_id
        self.level = level
        super().__init__()


class TaskStatusMessage(Message):
    """Message de statut de tâche pour mettre à jour les widgets UI."""
    
    def __init__(self, node_id: str, status: str, 
                 progress: float = 0.0, message: str = "") -> None:
        super().__init__()
        self.node_id = node_id
        self.status = status  # "started", "running", "completed", "failed"
        self.progress = progress
        self.message = message
