"""
Tests unitaires pour les intents et leurs IDs.
"""
import pytest
from fsdeploy.lib.scheduler.model.intent import IntentID, Intent

def test_intent_id_basics():
    id1 = IntentID("1")
    assert id1.get() == "1"
    assert str(id1) == "1"
    assert id1.depth == 1
    assert id1.parent_value is None

def test_intent_id_next_child():
    parent = IntentID("5")
    child = parent.next_child()
    assert child.get() == "5.1"
    assert child.depth == 2
    assert child.parent_value == "5"
    child2 = parent.next_child()
    assert child2.get() == "5.2"

def test_intent_id_equality():
    id1 = IntentID("3")
    id2 = IntentID("3")
    id3 = IntentID("4")
    assert id1 == id2
    assert id1 != id3
    assert id1 == "3"
    assert id1 != "4"

def test_intent_id_hash():
    id1 = IntentID("7")
    id2 = IntentID("7")
    assert hash(id1) == hash(id2)

def test_intent_creation():
    intent = Intent(id="test", params={"key": "value"})
    assert intent.get_id() == "test"
    assert intent.params == {"key": "value"}
    assert intent.status == "pending"
    assert intent.parent is None
    assert intent.children == []
    assert intent.error is None

def test_intent_with_intent_id():
    id_obj = IntentID("9")
    intent = Intent(id=id_obj)
    assert intent.id == id_obj
    assert intent.get_id() == "9"

def test_intent_validate_default():
    intent = Intent()
    assert intent.validate() is True

def test_intent_build_tasks_not_implemented():
    class ConcreteIntent(Intent):
        pass  # ne pas implémenter build_tasks
    intent = ConcreteIntent()
    with pytest.raises(NotImplementedError):
        intent.build_tasks()

def test_intent_resolve_with_custom_build_tasks():
    from unittest.mock import Mock
    class MockTask:
        def __init__(self):
            self.id = None
            self.context = None
            self.meta = {}
    class GoodIntent(Intent):
        def build_tasks(self):
            task1 = MockTask()
            task2 = MockTask()
            return [task1, task2]
    intent = GoodIntent(id="parent")
    tasks = intent.resolve()
    assert len(tasks) == 2
    for i, task in enumerate(tasks):
        assert task.meta["intent_id"] == "parent"
        assert task.meta["intent_class"] == "GoodIntent"
        assert task.meta["step_index"] == i

def test_intent_add_child():
    parent = Intent(id="p")
    child = Intent(id="c")
    parent.add_child(child)
    assert child.parent is parent
    assert parent.children == [child]

def test_intent_create_child():
    class ChildIntent(Intent):
        pass
    parent = Intent(id="10")
    child = parent.create_child(ChildIntent, params={"x": 1})
    assert isinstance(child, ChildIntent)
    assert child.parent is parent
    assert child.params == {"x": 1}
    # Vérifie que l'ID de l'enfant est hiérarchique
    assert child.get_id().startswith("10.")

def test_intent_status_transitions():
    intent = Intent()
    intent.set_status("running")
    assert intent.status == "running"
    intent.mark_failed(ValueError("test"))
    assert intent.status == "failed"
    assert isinstance(intent.error, ValueError)

def test_intent_repr():
    intent = Intent(id="myid")
    repr_str = repr(intent)
    assert "myid" in repr_str
    assert intent.__class__.__name__ in repr_str

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
