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
