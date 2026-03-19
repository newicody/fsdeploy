"""
Intent Queue

Convertit les événements en intents.

Responsable de :

- générer les IntentID
- créer les intents
- gérer la file d'attente des intents

C'est le lien entre :

event → intent
"""

class IntentQueue:
    """
    File d'attente des intents.
    """

    def __init__(self):

        self.queue = []

        # compteur global d'ID racine
        self._counter = 0

    def create_intent(self, event):
        """
        Crée un intent à partir d'un événement.
        """
        pass


    def push(self, intent):
        """
        Ajoute un intent à la queue.
        """
        pass


    def pop(self):
        """
        Récupère le prochain intent.
        """
        pass


    def is_empty(self):
        """
        Vérifie si la queue est vide.
        """
        pass


