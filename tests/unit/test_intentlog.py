"""
Unit tests for IntentLog.
"""
import tempfile
import os
import sys
import json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from fsdeploy.lib.scheduler.intentlog.log import IntentLog, IntentLogEntry


class MockIntent:
    def __init__(self, intent_id, intent_class, params=None):
        self.intent_id = intent_id
        self.intent_class = intent_class
        self.params = params or {}

    def get_id(self):
        return self.intent_id


def test_intent_log_entry():
    entry = IntentLogEntry(
        intent_id="1.2",
        intent_class="PoolImportIntent",
        status="running",
        params={"pool": "tank"},
        traceback=None,
        context={"thread": 5}
    )
    d = entry.to_dict()
    assert d["id"] == "1.2"
    assert d["class"] == "PoolImportIntent"
    assert d["status"] == "running"
    assert d["params"]["pool"] == "tank"
    assert d.get("context") is not None
    assert d["context"]["thread"] == 5
    print("test_intent_log_entry passed")


def test_intent_log_basic():
    log_dir = tempfile.mkdtemp()
    log = IntentLog(log_dir=log_dir)
    intent = MockIntent("1.3", "DatasetListIntent", {"pool": "all"})
    entry = log.record_start(intent, context={"start_time": 1000})
    assert entry.intent_id == "1.3"
    # simulate success
    log.record_success(entry, tasks_completed=2)
    assert entry.status == "completed"
    assert entry.duration > 0
    # check history
    hist = log.get_history(limit=5)
    assert len(hist) == 1
    assert hist[0]["status"] == "completed"
    # failure with context
    intent2 = MockIntent("1.4", "PoolImportIntent", {"pool": "tank"})
    entry2 = log.record_start(intent2)
    error = ValueError("Pool not found")
    log.record_failure(entry2, error, context={"disk": "/dev/sda1"})
    assert entry2.status == "failed"
    assert "Pool not found" in entry2.error
    assert entry2.context is not None
    # get failures
    fails = log.get_failures(limit=5)
    assert len(fails) == 1
    assert fails[0]["error"] == "Pool not found"
    assert fails[0].get("context", {}).get("disk") == "/dev/sda1"
    # counts
    assert log.total_count == 2
    assert log.failure_count == 1
    print("test_intent_log_basic passed")


def test_persistent_log():
    # create a temporary log file
    tmpdir = tempfile.mkdtemp()
    log_path = os.path.join(tmpdir, "intent.log")
    log = IntentLog(log_dir=tmpdir)
    intent = MockIntent("2.1", "TestIntent", {"value": 42})
    entry = log.record_start(intent)
    log.record_success(entry, 1)
    # verify file exists and contains JSONL
    assert os.path.exists(log_path)
    with open(log_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["id"] == "2.1"
        assert data["status"] == "completed"
    # add a failure with traceback
    intent2 = MockIntent("2.2", "FailingIntent")
    entry2 = log.record_start(intent2)
    try:
        raise RuntimeError("Simulated error")
    except RuntimeError as e:
        log.record_failure(entry2, e, context={"step": "mount"})
    # read again
    with open(log_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        assert len(lines) == 2
        second = json.loads(lines[1])
        assert second["status"] == "failed"
        assert "traceback" in second
        assert second.get("context", {}).get("step") == "mount"
    print("test_persistent_log passed")


if __name__ == "__main__":
    test_intent_log_entry()
    test_intent_log_basic()
    test_persistent_log()
    print("All intentlog tests passed!")
