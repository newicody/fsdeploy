from queue import Queue
from scheduler.model.runtime import RuntimeState

class Runtime:

    def __init__(self):
        self.event_queue = Queue()
        self.intent_queue = Queue()
        self.waiting_queue = []

        self.state = RuntimeState()

    def can_run(self, resources):
        return True

    def add_running(self, intent):
        pass

    def add_waiting(self, intent):
        self.waiting_queue.append(intent)

    def remove_waiting(self, intent):
        if intent in self.waiting_queue:
            self.waiting_queue.remove(intent)

    def fail(self, obj, error):
        print(f"[Runtime] Error: {obj} -> {error}")


