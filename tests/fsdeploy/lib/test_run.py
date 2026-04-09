"""
test_run.py — Validation du scheduler complet.

Usage : cd lib && python3 test_run.py
"""

from scheduler.core.scheduler import Scheduler
from scheduler.core.executor import Executor
from scheduler.core.resolver import Resolver
from scheduler.core.runtime import Runtime
from scheduler.security.resolver import SecurityResolver

from intents.test_intent import TestIntent
from scheduler.model.event import Event, CLIEvent


def test_basic():
    """Test basique : intent → task → execution."""
    print("=" * 60)
    print("TEST 1: Basic intent execution")
    print("=" * 60)

    runtime = Runtime()
    security = SecurityResolver()
    resolver = Resolver(security_resolver=security)
    executor = Executor(runtime)
    scheduler = Scheduler(resolver=resolver, executor=executor, runtime=runtime)

    # Créer un intent et le pousser
    intent = TestIntent(
        id="test1",
        params={"value": 21},
        context={"role": "admin"},
    )
    runtime.intent_queue.put(intent)

    # Un seul cycle
    scheduler.run_once()

    print(f"\nState: {runtime.summary()}")
    print(f"Completed: {runtime.state.completed}")
    assert runtime.state.completed_count > 0, "No tasks completed!"
    print("\n✅ TEST 1 PASSED\n")


def test_event_flow():
    """Test : event → intent → task via handler."""
    print("=" * 60)
    print("TEST 2: Event → Intent flow")
    print("=" * 60)

    runtime = Runtime()
    security = SecurityResolver()
    resolver = Resolver(security_resolver=security)
    executor = Executor(runtime)
    scheduler = Scheduler(resolver=resolver, executor=executor, runtime=runtime)

    # Enregistrer un handler
    def handle_test_event(event):
        return [TestIntent(
            params={"value": event.params.get("x", 0)},
            context={"role": "admin", "event": event},
        )]

    runtime.intent_queue.register_handler("test.compute", handle_test_event)

    # Émettre un event
    runtime.event_queue.put(Event(name="test.compute", params={"x": 50}))

    # Un seul cycle
    scheduler.run_once()

    print(f"\nState: {runtime.summary()}")
    assert runtime.state.completed_count > 0, "No tasks completed!"
    print("\n✅ TEST 2 PASSED\n")


def test_cli_event():
    """Test : CLI event dispatch."""
    print("=" * 60)
    print("TEST 3: CLI event dispatch")
    print("=" * 60)

    runtime = Runtime()
    security = SecurityResolver()
    resolver = Resolver(security_resolver=security)
    executor = Executor(runtime)
    scheduler = Scheduler(resolver=resolver, executor=executor, runtime=runtime)

    def handle_cli(event):
        return [TestIntent(
            params={"value": 99},
            context={"role": "admin"},
        )]

    runtime.intent_queue.register_handler("cli.test", handle_cli)

    runtime.event_queue.put(CLIEvent(command="test", args={"verbose": True}))
    scheduler.run_once()

    print(f"\nState: {runtime.summary()}")
    assert runtime.state.completed_count > 0, "No tasks completed!"
    print("\n✅ TEST 3 PASSED\n")


if __name__ == "__main__":
    test_basic()
    test_event_flow()
    test_cli_event()
    print("=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)
