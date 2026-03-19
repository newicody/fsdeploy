class TestTask:

    def __init__(self, id=None, params=None, context=None):
        self.id = id
        self.params = params or {}
        self.context = context or {}
        self.runtime = None

    # -------------------------
    def set_runtime(self, runtime):
        self.runtime = runtime

    # -------------------------
    # (optionnel)
    def required_resources(self):
        return ["cpu"]

    # -------------------------
    def before_run(self):
        print(f"[Task {self.id}] starting")

    # -------------------------
    def run(self):
        value = self.params.get("value", 0)
        result = value * 2

        print(f"[Task {self.id}] run -> {result}")
        return result

    # -------------------------
    def after_run(self):
        print(f"[Task {self.id}] finished")
