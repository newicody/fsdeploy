class Intent:

    def __init__(self, id=None, params=None, context=None):
        self.id = id
        self.params = params or {}
        self.context = context or {}

    # -------------------------
    # VALIDATION (optionnelle)
    # -------------------------
    def validate(self):
        return True

    # -------------------------
    # ENTRY POINT
    # -------------------------
    def resolve(self):
        """
        Transforme l'intent en liste de tasks.
        NE DOIT PAS exécuter quoi que ce soit.
        """

        tasks = self.build_tasks()

        if tasks is None:
            return []

        if not isinstance(tasks, list):
            raise ValueError("Intent.resolve() must return a list of tasks")

        # 🔹 enrichissement automatique (optionnel mais propre)
        for i, task in enumerate(tasks):
            if not hasattr(task, "meta"):
                task.meta = {}

            task.meta.update({
                "intent_id": self.id,
                "step_index": i
            })

        return tasks

    # -------------------------
    # À implémenter
    # -------------------------
    def build_tasks(self):
        raise NotImplementedError("Intent must implement build_tasks()")
