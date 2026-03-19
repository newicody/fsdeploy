"""
Event Queue

File d'attente des événements entrants.

Sources possibles :

- CLI
- bus (socket / dbus / udev)
- scheduler interne
- cron
- init system

Cette queue est le point d'entrée du scheduler.
"""

class EventQueue:
    """
    File d'attente des événements.
    """

    def __init__(self):

        self.queue = []

    def push(self, event):
        """
        Ajoute un événement à la queue.
        """
        pass


    def pop(self):
        """
        Récupère le prochain événement.
        """
        pass


    def is_empty(self):
        """
        Vérifie si la queue est vide.
        """
        pass
