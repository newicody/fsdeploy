"""
Runtime State

Représente l'état courant du scheduler en mémoire.

Contient :

- les intents en cours d'exécution
- les intents en attente
- les locks actifs
- les ressources utilisées

Ce composant est critique pour :

- le parallélisme
- la gestion des conflits
- le monitoring en temps réel
"""

class RuntimeState:

    def __init__(self):
        self.running = {}
        self.completed = {}
        self.failed = {}

    # -------------------------
    # START
    # -------------------------
    def start(self, task):
        self.running[task.id] = {
            "task": task,
            "status": "running"
        }

    # -------------------------
    # SUCCESS
    # -------------------------
    def success(self, task, result):
        self.running.pop(task.id, None)

        self.completed[task.id] = {
            "task": task,
            "result": result,
            "status": "success"
        }

    # -------------------------
    # FAILURE
    # -------------------------
    def fail(self, task, error):
        self.running.pop(task.id, None)

        self.failed[task.id] = {
            "task": task,
            "error": error,
            "status": "failed"
        }

    def is_running(self, task):
        return task.id in self.running

    def add_running(self, intent):
        """
        Ajoute un intent en cours d'exécution.
        """
        pass


    def remove_running(self, intent_id):
        """
        Supprime un intent des tâches en cours.
        """
        pass


    def add_waiting(self, intent):
        """
        Ajoute un intent en attente.
        """
        pass


    def pop_waiting(self):
        """
        Récupère un intent en attente.
        """
        pass

    def add_lock(self, lock):
        """
        Ajoute un lock actif.
        """
        pass


    def remove_lock(self, resource_id):
        """
        Supprime un lock.
        """
        pass


    def is_locked(self, resource_id):
        """
        Vérifie si une ressource est verrouillée.
        """
        pass


    def get_lock(self, resource_id):
        """
        Retourne le lock associé à une ressource.
        """
        pass

    def add_resource(self, resource):
        """
        Enregistre une ressource.
        """
        pass


    def get_resource(self, resource_id):
        """
        Retourne une ressource.
        """
        pass

    def can_run(self, resources):
        """
        Vérifie si une liste de ressources est disponible.

        Retourne True si aucune ressource n'est lockée.
        """
        pass
