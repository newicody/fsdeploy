"""
Intent model

Un intent représente une intention d'exécution dans le scheduler.
"""

class IntentID:
    """
    Identifiant hiérarchique d’un intent.
    """

    def __init__(self, value):
        self.value = str(value)
        self._child_counter = 0

    def next_child(self):
        """
        Génère un nouvel ID enfant.
        ex :
        1 → 1.1 → 1.2
        """
        self._child_counter += 1
        return IntentID(f"{self.value}.{self._child_counter}")

    def get(self):
        """
        Retourne la valeur de l'ID.
        """
        return self.value


class Intent:

    def __init__(self, id=None, params=None, context=None):
        self.id = id if isinstance(id, IntentID) else IntentID(id or "0")

        self.params = params or {}
        self.context = context or {}

        # 🔹 état
        self.status = "pending"

        # 🔹 hiérarchie
        self.parent = None
        self.children = []

    # -------------------------
    # VALIDATION
    # -------------------------
    def validate(self):
        return True

    # -------------------------
    # RESOLUTION (ENTRY POINT)
    # -------------------------
    def resolve(self):
        """
        Transforme l'intent en liste de tasks.
        """

        tasks = self.build_tasks()

        if tasks is None:
            return []

        if not isinstance(tasks, list):
            raise ValueError("Intent.resolve() must return a list")

        # 🔹 enrichissement automatique
        for i, task in enumerate(tasks):

            # ID hiérarchique pour la task
            child_id = self.id.next_child()

            if hasattr(task, "id"):
                task.id = child_id.get()

            # context propagation
            if hasattr(task, "context"):
                task.context = self.context

            # metadata utile
            if not hasattr(task, "meta"):
                task.meta = {}

            task.meta.update({
                "intent_id": self.id.get(),
                "step_index": i
            })

        return tasks

    # -------------------------
    # À implémenter
    # -------------------------
    def build_tasks(self):
        raise NotImplementedError("Intent must implement build_tasks()")

    # -------------------------
    # STATUS
    # -------------------------
    def set_status(self, status):
        self.status = status

    # -------------------------
    # HIERARCHY
    # -------------------------
    def add_child(self, intent):
        intent.parent = self
        self.children.append(intent)

    # -------------------------
    # GETTERS
    # -------------------------
    def get_id(self):
        return self.id.get()

    def get_event(self):
        return self.context.get("event")
