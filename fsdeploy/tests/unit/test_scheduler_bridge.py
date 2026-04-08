"""
Tests unitaires pour le SchedulerBridge.
"""
import time
import uuid
from unittest.mock import MagicMock, patch
import pytest

from fsdeploy.lib.scheduler.bridge import SchedulerBridge, Ticket
from fsdeploy.lib.scheduler.model.event import BridgeEvent, register_bridge_event_handler


class DummyIntent:
    def __init__(self):
        self.params = {}
        self.context = {}


def test_submit_event_creates_ticket():
    bridge = SchedulerBridge()
    # Mock scheduler and its event_queue
    mock_scheduler = MagicMock()
    mock_queue = MagicMock()
    mock_scheduler.event_queue = mock_queue
    with patch.object(bridge, '_get_scheduler', return_value=mock_scheduler):
        ticket_id = bridge.submit_event("detection.start", pools=["tank"])
        assert ticket_id.startswith("sch-")
        # Ticket stored
        ticket = bridge.get_ticket(ticket_id)
        assert ticket is not None
        assert ticket.event_name == "detection.start"
        assert ticket.params == {"pools": ["tank"]}
        # Event pushed to queue
        assert mock_queue.put.called
        event = mock_queue.put.call_args[0][0]
        assert isinstance(event, BridgeEvent)
        assert event.name == "detection.start"
        assert event.params["pools"] == ["tank"]
        assert event.params["_bridge_ticket"] == ticket_id
        assert event.source == "bridge"


def test_submit_intent_creates_ticket():
    bridge = SchedulerBridge()
    mock_scheduler = MagicMock()
    mock_intent_queue = MagicMock()
    mock_scheduler.intent_queue = mock_intent_queue
    with patch.object(bridge, '_get_scheduler', return_value=mock_scheduler):
        intent = DummyIntent()
        ticket_id = bridge.submit(intent)
        assert ticket_id.startswith("sch-intent-")
        ticket = bridge.get_ticket(ticket_id)
        assert ticket is not None
        assert "intent.DummyIntent" in ticket.event_name
        assert intent.context.get("_bridge_ticket") == ticket_id
        # Intent pushed to queue
        assert mock_intent_queue.push.called
        pushed_intent = mock_intent_queue.push.call_args[0][0]
        assert pushed_intent is intent


def test_poll_updates_ticket_from_completed():
    bridge = SchedulerBridge()
    # Create a pending ticket
    ticket_id = f"sch-{uuid.uuid4().hex[:8]}"
    ticket = Ticket(
        id=ticket_id,
        event_name="test.event",
        params={},
        submitted_at=time.time(),
        status="pending",
    )
    with bridge._lock:
        bridge._tickets[ticket_id] = ticket

    # Mock runtime state with completed entry
    mock_state = MagicMock()
    mock_state.completed = {
        "task1": {
            "task": MagicMock(context={"_bridge_ticket": ticket_id}),
            "result": {"success": True},
        }
    }
    mock_state.failed = {}
    mock_runtime = MagicMock()
    mock_runtime.state = mock_state
    with patch.object(bridge, '_get_runtime_state', return_value=mock_runtime):
        done = bridge.poll()
        assert len(done) == 1
        assert done[0].id == ticket_id
        assert done[0].status == "completed"
        assert done[0].result == {"success": True}
        # Ticket is now completed in storage
        stored = bridge.get_ticket(ticket_id)
        assert stored.status == "completed"


def test_poll_updates_ticket_from_failed():
    bridge = SchedulerBridge()
    ticket_id = f"sch-{uuid.uuid4().hex[:8]}"
    ticket = Ticket(
        id=ticket_id,
        event_name="test.event",
        params={},
        submitted_at=time.time(),
        status="pending",
    )
    with bridge._lock:
        bridge._tickets[ticket_id] = ticket

    mock_state = MagicMock()
    mock_state.completed = {}
    mock_state.failed = {
        "task1": {
            "task": MagicMock(context={"_bridge_ticket": ticket_id}),
            "error": "Something went wrong",
        }
    }
    mock_runtime = MagicMock()
    mock_runtime.state = mock_state
    with patch.object(bridge, '_get_runtime_state', return_value=mock_runtime):
        done = bridge.poll()
        assert len(done) == 1
        assert done[0].id == ticket_id
        assert done[0].status == "failed"
        assert "Something went wrong" in done[0].error


def test_on_result_callback():
    bridge = SchedulerBridge()
    ticket_id = f"sch-{uuid.uuid4().hex[:8]}"
    ticket = Ticket(
        id=ticket_id,
        event_name="test.event",
        params={},
        submitted_at=time.time(),
        status="pending",
    )
    with bridge._lock:
        bridge._tickets[ticket_id] = ticket

    callback_called = []
    def my_callback(t):
        callback_called.append(t.id)

    bridge.on_result(ticket_id, my_callback)
    # callback not called yet because ticket pending
    assert len(callback_called) == 0

    # Simulate ticket completed via poll
    mock_state = MagicMock()
    mock_state.completed = {
        "task1": {
            "task": MagicMock(context={"_bridge_ticket": ticket_id}),
            "result": {},
        }
    }
    mock_state.failed = {}
    mock_runtime = MagicMock()
    mock_runtime.state = mock_state
    with patch.object(bridge, '_get_runtime_state', return_value=mock_runtime):
        bridge.poll()
        # callback should have been triggered
        assert len(callback_called) == 1
        assert callback_called[0] == ticket_id


def test_submit_event_with_custom_priority():
    bridge = SchedulerBridge()
    mock_scheduler = MagicMock()
    mock_queue = MagicMock()
    mock_scheduler.event_queue = mock_queue
    with patch.object(bridge, '_get_scheduler', return_value=mock_scheduler):
        ticket_id = bridge.submit_event("test.event", priority=-200, foo="bar")
        assert ticket_id.startswith("sch-")
        event = mock_queue.put.call_args[0][0]
        assert event.priority == -200
        assert event.params["foo"] == "bar"
        assert event.params["_bridge_ticket"] == ticket_id


def test_pending_count_and_tickets():
    bridge = SchedulerBridge()
    # No tickets initially
    assert bridge.pending_count == 0
    assert bridge.pending_tickets == []
    # Add a pending ticket manually
    ticket = Ticket(
        id="test1",
        event_name="test1",
        params={},
        submitted_at=time.time(),
        status="pending",
    )
    with bridge._lock:
        bridge._tickets["test1"] = ticket
    assert bridge.pending_count == 1
    pending = bridge.pending_tickets
    assert len(pending) == 1
    assert pending[0].id == "test1"
    # Add a completed ticket
    ticket2 = Ticket(
        id="test2",
        event_name="test2",
        params={},
        submitted_at=time.time(),
        status="completed",
    )
    with bridge._lock:
        bridge._tickets["test2"] = ticket2
    assert bridge.pending_count == 1  # still only one pending
    assert len(bridge.pending_tickets) == 1


def test_clear_done():
    bridge = SchedulerBridge()
    # Add pending, completed, failed tickets
    with bridge._lock:
        bridge._tickets["p1"] = Ticket(id="p1", status="pending")
        bridge._tickets["c1"] = Ticket(id="c1", status="completed")
        bridge._tickets["f1"] = Ticket(id="f1", status="failed")
    removed = bridge.clear_done()
    assert removed == 2  # completed and failed
    with bridge._lock:
        assert "p1" in bridge._tickets
        assert "c1" not in bridge._tickets
        assert "f1" not in bridge._tickets


def test_get_scheduler_state_fallback():
    bridge = SchedulerBridge()
    with patch.object(bridge, '_get_scheduler', return_value=None):
        state = bridge.get_scheduler_state()
        # Should return fallback dict with expected keys
        assert isinstance(state, dict)
        assert "event_count" in state
        assert "intent_count" in state
        assert "task_count" in state
        assert "completed_count" in state
        assert "active_task" in state
        assert "recent_tasks" in state


def test_bridge_event_to_intents():
    # Register a dummy handler
    handler_called = []
    def dummy_handler(event):
        handler_called.append(event.name)
        return []  # no intents
    register_bridge_event_handler("test.handler", dummy_handler)
    # Create BridgeEvent
    from fsdeploy.lib.scheduler.model.event import BridgeEvent
    event = BridgeEvent(name="test.handler", params={"foo": 1}, source="test")
    intents = event.to_intents()
    # Handler should have been called
    assert len(handler_called) == 1
    assert handler_called[0] == "test.handler"
    assert intents == []
    # Event with no handler should return empty list
    event2 = BridgeEvent(name="unknown.event", params={})
    intents2 = event2.to_intents()
    assert intents2 == []


def test_wait_for_ticket_success():
    bridge = SchedulerBridge()
    ticket_id = f"sch-{uuid.uuid4().hex[:8]}"
    ticket = Ticket(
        id=ticket_id,
        event_name="test",
        params={},
        submitted_at=time.time(),
        status="pending",
    )
    with bridge._lock:
        bridge._tickets[ticket_id] = ticket

    # Simulate completion after a short delay
    def complete_soon():
        time.sleep(0.05)
        with bridge._lock:
            ticket.status = "completed"
            ticket.result = {"done": True}

    import threading
    t = threading.Thread(target=complete_soon)
    t.start()
    # wait with timeout longer than completion
    success = bridge.wait_for_ticket(ticket_id, timeout=1.0)
    t.join()
    assert success is True
    assert bridge.is_done(ticket_id)
    assert bridge.get_result(ticket_id) == {"done": True}


def test_wait_for_ticket_timeout():
    bridge = SchedulerBridge()
    ticket_id = f"sch-{uuid.uuid4().hex[:8]}"
    ticket = Ticket(
        id=ticket_id,
        event_name="test",
        params={},
        submitted_at=time.time(),
        status="pending",
    )
    with bridge._lock:
        bridge._tickets[ticket_id] = ticket

    # Ticket stays pending, wait should timeout
    start = time.time()
    success = bridge.wait_for_ticket(ticket_id, timeout=0.1)
    elapsed = time.time() - start
    assert elapsed >= 0.1
    assert success is False
    assert not bridge.is_done(ticket_id)


def test_get_tickets_by_status():
    bridge = SchedulerBridge()
    # Clear any existing tickets
    with bridge._lock:
        bridge._tickets.clear()

    ids = []
    for i in range(5):
        tid = f"sch-{uuid.uuid4().hex[:8]}"
        status = "pending" if i % 2 == 0 else "completed"
        ticket = Ticket(
            id=tid,
            event_name=f"test{i}",
            params={},
            submitted_at=time.time(),
            status=status,
        )
        with bridge._lock:
            bridge._tickets[tid] = ticket
        ids.append(tid)

    pending = bridge.get_tickets_by_status("pending")
    completed = bridge.get_tickets_by_status("completed")
    assert len(pending) == 3  # indices 0,2,4
    assert len(completed) == 2
    for t in pending:
        assert t.status == "pending"
    for t in completed:
        assert t.status == "completed"


def test_cleanup_old():
    bridge = SchedulerBridge()
    with bridge._lock:
        bridge._tickets.clear()
    # Create recent completed, old completed, old failed, pending
    now = time.time()
    recent = Ticket(id="recent", status="completed", submitted_at=now - 100)
    old_completed = Ticket(id="oldc", status="completed", submitted_at=now - 4000)
    old_failed = Ticket(id="oldf", status="failed", submitted_at=now - 5000)
    pending = Ticket(id="pend", status="pending", submitted_at=now - 6000)
    with bridge._lock:
        for t in (recent, old_completed, old_failed, pending):
            bridge._tickets[t.id] = t
    # Cleanup older than 1 hour (3600 seconds)
    removed = bridge.cleanup_old(max_age_seconds=3600)
    assert removed == 2  # old_completed and old_failed
    with bridge._lock:
        assert "recent" in bridge._tickets
        assert "oldc" not in bridge._tickets
        assert "oldf" not in bridge._tickets
        assert "pend" in bridge._tickets
    # Cleanup with very short age
    removed2 = bridge.cleanup_old(max_age_seconds=10)
    assert removed2 == 1  # recent completed is older than 10 seconds? It's 100 sec old, yes
    with bridge._lock:
        assert "recent" not in bridge._tickets
        assert "pend" in bridge._tickets  # still pending, not removed


def test_submit_event_fallback():
    bridge = SchedulerBridge()
    # Simuler un scheduler sans event_queue
    mock_scheduler = MagicMock()
    mock_scheduler.event_queue = None  # pas de queue
    with patch.object(bridge, '_get_scheduler', return_value=mock_scheduler):
        # Mock le bus d'événements
        mock_bus = MagicMock()
        bridge._event_bus = mock_bus
        ticket_id = bridge.submit_event("test.fallback", foo="bar")
        assert ticket_id.startswith("sch-")
        # Vérifier que le ticket a été créé
        ticket = bridge.get_ticket(ticket_id)
        assert ticket is not None
        # Vérifier que le bus a été appelé
        assert mock_bus.emit.called
        call_args = mock_bus.emit.call_args
        assert call_args[0][0] == "bridge.event"
        data = call_args[0][1]
        assert data["name"] == "test.fallback"
        assert data["params"]["foo"] == "bar"
        assert data["_bridge_ticket"] == ticket_id
        # Vérifier que le scheduler.event_queue.put n'a pas été appelé
        assert not hasattr(mock_scheduler, 'event_queue') or not mock_scheduler.event_queue
        # Vérifier que le ticket est toujours en pending (car aucun traitement)
        assert ticket.status == "pending"


def test_submit_event_fallback_no_bus():
    bridge = SchedulerBridge()
    # Pas de scheduler
    with patch.object(bridge, '_get_scheduler', return_value=None):
        # Pas de bus d'événements non plus
        bridge._event_bus = None
        # Cela ne doit pas lever d'exception
        ticket_id = bridge.submit_event("test.no_bus", foo="baz")
        assert ticket_id.startswith("sch-")
        ticket = bridge.get_ticket(ticket_id)
        assert ticket is not None
        # Le ticket reste pending
        assert ticket.status == "pending"


def test_reset_tickets():
    bridge = SchedulerBridge()
    with bridge._lock:
        bridge._tickets.clear()
    # Ajouter quelques tickets
    for i in range(5):
        ticket = Ticket(id=f"t{i}", status="pending")
        with bridge._lock:
            bridge._tickets[ticket.id] = ticket
    # Ajouter un historique
    ticket_hist = Ticket(id="hist", status="completed")
    bridge._history.append(ticket_hist)
    # Reset
    removed = bridge.reset_tickets()
    assert removed == 5  # seul les tickets dans _tickets, pas l'historique? L'historique est vidé aussi, mais _history n'est pas compté.
    # En réalité, reset_tickets retourne len(self._tickets) avant clear, et vide aussi _history.
    # Nous avons ajouté 5 tickets dans _tickets, donc 5.
    with bridge._lock:
        assert len(bridge._tickets) == 0
    assert len(bridge.history) == 0


def test_get_all_tickets():
    bridge = SchedulerBridge()
    with bridge._lock:
        bridge._tickets.clear()
    tickets = []
    for i in range(3):
        ticket = Ticket(id=f"t{i}", status="pending" if i % 2 == 0 else "completed")
        tickets.append(ticket)
        with bridge._lock:
            bridge._tickets[ticket.id] = ticket
    all_tickets = bridge.get_all_tickets()
    assert len(all_tickets) == 3
    ids = {t.id for t in all_tickets}
    assert ids == {"t0", "t1", "t2"}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
