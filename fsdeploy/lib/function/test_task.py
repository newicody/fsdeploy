"""
Test task — validation du scheduler.
"""

from scheduler.model.task import Task


class TestTask(Task):

    def required_resources(self):
        return []

    def before_run(self):
        print(f"[Task {self.id}] starting")

    def run(self):
        value = self.params.get("value", 0)
        result = value * 2
        print(f"[Task {self.id}] run -> {result}")
        return result

    def after_run(self):
        print(f"[Task {self.id}] finished")
