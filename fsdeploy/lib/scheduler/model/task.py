class Task:
    executor = "default"

    def __init__(self, id=None, params=None):
        self.id = id
        self.params = params or {}

    def set_runtime(self, runtime):
        self.runtime = runtime

    def before_run(self):
        pass

    def run(self):
        raise NotImplementedError()

    def after_run(self):
        pass
