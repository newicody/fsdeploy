"""
Tests unitaires pour la file d'intents.
"""

import threading
import time
import pytest
from fsdeploy.lib.scheduler.queue.intent_queue import IntentQueue


class MockIntent:
    def __init__(self, intent_id=None):
        self.id = intent_id


class MockEvent:
    def __init__(self, name):
        self.name = name


def test_push_pop():
    q = IntentQueue()
    intent = MockIntent()
    q.push(intent)
    popped = q.pop()
    assert popped is intent
    assert q.empty()


def test_pop_many():
    q = IntentQueue()
    intents = [MockIntent() for _ in range(5)]
    for i in intents:
        q.push(i)
    # pop_many with n=3
    popped = q.pop_many(3)
    assert len(popped) == 3
    assert popped == intents[:3]
    # Remaining should be 2
    assert q.qsize() == 2
    # pop remaining with n larger
    popped2 = q.pop_many(10)
    assert len(popped2) == 2
    assert popped2 == intents[3:]


def test_pop_many_with_timeout():
    q = IntentQueue()
    # No items, timeout 0.1 -> returns empty list
    popped = q.pop_many(5, timeout=0.1)
    assert popped == []
    # Add items after a short delay in another thread
    def add_later():
        time.sleep(0.05)
        q.push(MockIntent())
    threading.Thread(target=add_later).start()
    popped = q.pop_many(1, timeout=0.2)
    assert len(popped) == 1
    assert q.empty()


def test_register_handler():
    q = IntentQueue()
    def handler(event):
        return [MockIntent()]
    q.register_handler("test.event", handler)
    # Create event and convert
    event = MockEvent("test.event")
    intents = q.create_from_event(event)
    assert len(intents) == 1
    # Check that intent got an ID
    assert intents[0].id is not None
    assert intents[0].id.get() != "0"


def test_wildcard_handler():
    q = IntentQueue()
    calls = []
    def wild_handler(event):
        calls.append(event.name)
        return []
    q.register_handler("*", wild_handler)
    event = MockEvent("some.unknown")
    q.create_from_event(event)
    assert "some.unknown" in calls


def test_queue_size_and_empty():
    q = IntentQueue()
    assert q.empty()
    assert q.qsize() == 0
    q.push(MockIntent())
    assert not q.empty()
    assert q.qsize() == 1


if __name__ == "__main__":
    pytest.main([__file__])
