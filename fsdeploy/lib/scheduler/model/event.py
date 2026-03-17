"""
Event model

Représente un événement dans le système fsdeploy.

Les événements sont la source de toutes les actions du scheduler.

Flux général :

event → intent → task → execution

Un événement peut provenir de plusieurs sources :

- scheduler
- cli
- bus (socket / dbus / udev)
- init system
- cron
- internal task
"""

class Event:
    """
    Représente un événement déclenché dans le système.
    """

    def __init__(self, name, params=None, source=None, parent_id=None):

        # nom de l'événement
        self.name = name

        # paramètres associés
        self.params = params or {}

        # source de l'événement
        self.source = source

        # identifiant parent pour propagation
        self.parent_id = parent_id

        # timestamp (rempli par le scheduler)
        self.time = None

    def set_time(self, timestamp):
        """
        Définit le timestamp de l'événement.
        """
        pass


    def get_name(self):
        """
        Retourne le nom de l'événement.
        """
        pass


    def get_params(self):
        """
        Retourne les paramètres de l'événement.
        """
        pass


    def get_source(self):
        """
        Retourne la source de l'événement.
        """
        pass
