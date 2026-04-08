"""
Tests unitaires du pont UI‑scheduler.
"""
import pytest
from unittest.mock import Mock, patch
from fsdeploy.lib.scheduler.bridge import SchedulerBridge

def test_bridge_singleton():
    b1 = SchedulerBridge.default()
    b2 = SchedulerBridge.default()
    assert b1 is b2

def test_get_scheduler_state_fallback():
    bridge = SchedulerBridge.default()
    # Simuler l'absence de scheduler
    with patch.object(bridge, '_get_scheduler', return_value=None):
        state = bridge.get_scheduler_state()
        assert isinstance(state, dict)
        assert "event_count" in state
        assert "intent_count" in state
        assert "task_count" in state
        assert "completed_count" in state
        # Les valeurs sont générées aléatoirement, on ne vérifie que les clés.

def test_get_scheduler_state_with_real_scheduler():
    bridge = SchedulerBridge.default()
    mock_scheduler = Mock()
    mock_scheduler.state_snapshot.return_value = {
        "event_count": 42,
        "intent_count": 7,
        "task_count": 3,
        "completed_count": 100,
        "active_task": {"id": "task1"},
        "recent_tasks": []
    }
    with patch.object(bridge, '_get_scheduler', return_value=mock_scheduler):
        state = bridge.get_scheduler_state()
        assert state["event_count"] == 42
        assert state["intent_count"] == 7
        mock_scheduler.state_snapshot.assert_called_once()

def test_submit_emits_bus_event():
    from fsdeploy.lib.scheduler.model.intent import Intent
    from fsdeploy.lib.bus.event_bus import MessageBus
    class DummyIntent(Intent):
        def build_tasks(self):
            return []
    intent = DummyIntent(id="test")
    bridge = SchedulerBridge.default()
    # Mock du bus pour vérifier l'appel à emit
    mock_bus = Mock()
    with patch('fsdeploy.lib.bus.event_bus.MessageBus.global_instance', return_value=mock_bus):
        future = bridge.submit(intent)
        # Vérifie que emit a été appelé avec le bon type d'événement
        mock_bus.emit.assert_called_once_with("intent.submitted", {"intent": intent})
        # La future doit être résolue avec None pour l'instant
        assert future.done()
        assert future.result() is None

def test_submit_with_future():
    from fsdeploy.lib.scheduler.model.intent import Intent
    class DummyIntent(Intent):
        def build_tasks(self):
            return []
    intent = DummyIntent(id="test")
    bridge = SchedulerBridge.default()
    future = bridge.submit(intent)
    # La future doit être terminée (car on a mis un set_result immédiat)
    assert future.done()
    # Le résultat est None (implémentation temporaire)
    assert future.result() is None
    # Vérifier que la future est bien une instance de Future
    from concurrent.futures import Future
    assert isinstance(future, Future)

def test_bridge_init():
    bridge = SchedulerBridge()
    assert bridge._scheduler is None
    assert bridge._event_bus is None

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
