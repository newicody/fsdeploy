from scheduler.model.intent import Intent
from function.test_task import TestTask


class TestIntent(Intent):

    def build_tasks(self):

        value = self.params.get("value", 1)

        return [
            TestTask(
                id=f"{self.id}_task",
                params={"value": value},
                context=self.context
            )
        ]
