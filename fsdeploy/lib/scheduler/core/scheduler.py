class Scheduler:

    def __init__(self, resolver, executor, runtime):
        self.resolver = resolver
        self.executor = executor
        self.runtime = runtime

    def run(self):

        while True:
            self._process_events()
            self._process_intents()
            self._process_waiting()

    # -------------------------
    # EVENTS → INTENTS
    # -------------------------
    def _process_events(self):
        while not self.runtime.event_queue.empty():
            event = self.runtime.event_queue.get()

            intents = self._event_to_intents(event)

            for intent in intents:
                self.runtime.intent_queue.put(intent)

    def _event_to_intents(self, event):
        # Hook extensible
        if hasattr(event, "to_intents"):
            return event.to_intents()

        return []

    # -------------------------
    # INTENTS → TASKS → EXECUTION
    # -------------------------
    def _process_intents(self):
        while not self.runtime.intent_queue.empty():

            intent = self.runtime.intent_queue.get()
            try:
                # 🔹 validation intent
                if hasattr(intent, "validate"):
                    intent.validate()

                # 🔹 resolver (sécurité / ressources)
                tasks = intent.resolve()

                for task in tasks:

                    result = self.resolver.resolve(
                        task,
                        context=getattr(intent, "context", {})
                    )

                    resources = result.get("resources", [])
                    print("RESOURCES:", resources)

                    print("CAN RUN:", self.runtime.can_run(resources))
                    if self.runtime.can_run(resources):
                        task.set_runtime(self.runtime)   
                        self.runtime.add_running(task)
                        self.executor.execute(task)

                    else:
                        self.runtime.add_waiting(task)
            except Exception as e:
                self.runtime.fail(intent, e)

    # -------------------------
    # WAITING QUEUE
    # -------------------------
    def _process_waiting(self):

        for task in list(self.runtime.waiting_queue): 
            try:
                result = self.resolver.resolve(
                    task,
                    context=getattr(task, "context", {})
                )

                resources = result.get("resources", [])

                if self.runtime.can_run(resources):

                    self.runtime.remove_waiting(task)

                    task.set_runtime(self.runtime)   # 🔥 IMPORTANT
                    self.executor.execute(task)

            except Exception as e:
                self.runtime.fail(task, e)
