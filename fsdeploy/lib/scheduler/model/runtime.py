class RuntimeState:

    def __init__(self):
        self.running = {}
        self.waiting = {}
        self.locks = []

    # ------------------------
    # CHECK
    # ------------------------

    def can_run(self, locks):

        for new_lock in locks:
            for active_lock in self.locks:
                if new_lock.conflicts(active_lock):
                    return False

        return True

    # ------------------------
    # RUNNING
    # ------------------------

    def add_running(self, intent):

        self.running[intent.id] = intent

        for lock in intent.locks:
            self.locks.append(lock)

    def remove_running(self, intent_id):

        intent = self.running.pop(intent_id, None)
        if not intent:
            return

        for lock in intent.locks:
            try:
                self.locks.remove(lock)
            except ValueError:
                pass

    # ------------------------
    # WAITING
    # ------------------------

    def add_waiting(self, intent):
        self.waiting[intent.id] = intent

    def get_waiting(self):
        return list(self.waiting.values())

    def pop_waiting(self, intent_id):
        return self.waiting.pop(intent_id, None)
