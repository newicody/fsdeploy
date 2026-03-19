from scheduler.core.scheduler import Scheduler
from scheduler.core.executor import Executor
from scheduler.core.resolver import Resolver
from scheduler.security.resolver import SecurityResolver
from scheduler.core.runtime import Runtime

from intents.test_intent import TestIntent


# -------------------------
# SETUP
# -------------------------
runtime = Runtime()

security = SecurityResolver()
resolver = Resolver(security_resolver=security)

executor = Executor(runtime)

scheduler = Scheduler(
    resolver=resolver,
    executor=executor,
    runtime=runtime
)

# -------------------------
# TEST INTENT
# -------------------------
intent = TestIntent(
    id="test1",
    params={"value": 21},
    context={"role": "admin"}
)

runtime.intent_queue.put(intent)

# -------------------------
# RUN (1 cycle manuel)
# -------------------------
scheduler._process_intents()

# -------------------------
# CHECK RESULT
# -------------------------
print("\nSTATE COMPLETED:")
print(runtime.state.completed)
