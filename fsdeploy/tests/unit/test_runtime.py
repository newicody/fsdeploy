"""
Tests unitaires pour le module runtime (parallélisme, locks, retry).
"""

import time
import pytest
import os
from unittest.mock import patch
from fsdeploy.lib.scheduler.model.runtime import RuntimeState


class MockLock:
    def __init__(self, name):
        self.name = name

    def conflicts(self, other):
        # Simpler conflict: same name conflicts
        return self.name == other.name


class MockTask:
    def __init__(self, task_id, locks=None):
        self.id = task_id
        self.locks = locks or []


def test_runtime_initialization():
    # Isoler des variables d'environnement
    with patch.dict(os.environ, {}, clear=True):
        rt = RuntimeState()
        # max_parallel par défaut est 5
        assert rt.max_parallel == 5
        assert rt.waiting_count == 0
        assert rt.running_count == 0


def test_add_waiting():
    rt = RuntimeState()
    task = MockTask("task1")
    rt.add_waiting(task)
    assert rt.waiting_count == 1
    assert rt.get_waiting()[0].id == "task1"


def test_select_runnable_tasks_no_locks():
    rt = RuntimeState()
    for i in range(3):
        task = MockTask(f"task{i}")
        rt.add_waiting(task)
    runnable = rt.select_runnable_tasks(max_tasks=2)
    assert len(runnable) == 2
    # Should have been removed from waiting? No, select_runnable_tasks does not remove.
    assert rt.waiting_count == 3


def test_locks_conflict():
    rt = RuntimeState()
    lock_a = MockLock("pool")
    lock_b = MockLock("pool")
    lock_c = MockLock("dataset")
    assert rt._locks_conflict([lock_a], [lock_b]) is True
    assert rt._locks_conflict([lock_a], [lock_c]) is False


def test_can_run_without_conflict():
    rt = RuntimeState()
    lock_a = MockLock("pool")
    lock_b = MockLock("dataset")
    rt.acquire_locks([lock_a])
    # lock_b does not conflict
    assert rt.can_run([lock_b]) is True
    # lock_a conflicts with active lock_a
    assert rt.can_run([lock_a]) is False


def test_acquire_tasks():
    rt = RuntimeState()
    lock_a = MockLock("pool")
    lock_b = MockLock("dataset")
    task1 = MockTask("task1", [lock_a])
    task2 = MockTask("task2", [lock_b])
    rt.add_waiting(task1)
    rt.add_waiting(task2)
    acquired = rt.acquire_tasks(max_tasks=2)
    # Both can run because locks different
    assert len(acquired) == 2
    assert rt.waiting_count == 0
    assert rt.lock_count == 2


def test_acquire_tasks_with_conflict():
    rt = RuntimeState()
    lock = MockLock("pool")
    task1 = MockTask("task1", [lock])
    task2 = MockTask("task2", [lock])  # same lock, conflict
    rt.add_waiting(task1)
    rt.add_waiting(task2)
    acquired = rt.acquire_tasks(max_tasks=2)
    # Only one can be acquired due to lock conflict
    assert len(acquired) == 1
    assert rt.waiting_count == 1
    assert rt.lock_count == 1


def test_retry_counting():
    rt = RuntimeState()
    rt.increment_retry("task1")
    assert rt.get_retry_count("task1") == 1
    rt.clear_retry("task1")
    assert rt.get_retry_count("task1") == 0


def test_retry_info():
    rt = RuntimeState()
    # No retry yet
    info = rt.retry_info("taskX")
    assert info["count"] == 0
    assert info["last_failure"] is None
    assert info["next_retry_delay"] == 0.0
    # Simulate a failure
    rt.increment_retry("taskX")
    # Need to set timestamps and delays (they are set by fail() method)
    # For unit test, we can manually set them
    with rt._lock:
        rt._retry_timestamps["taskX"] = time.monotonic()
        rt._retry_delays["taskX"] = 2.0
    info = rt.retry_info("taskX")
    assert info["count"] == 1
    assert info["last_failure"] is not None
    assert info["next_retry_delay"] == 2.0
    # ready depends on time
    ready = rt.is_ready_for_retry("taskX")
    # Since we just set timestamp, likely not ready
    assert ready is False


def test_throughput():
    rt = RuntimeState()
    # Simulate completions
    now = time.monotonic()
    for i in range(5):
        rt._record_completion(now - 10.0)  # old
    for i in range(5):
        rt._record_completion(now - 1.0)   # recent
    tp = rt.throughput(window_seconds=5.0)
    # Should be roughly 1 per second (5/5)
    assert tp == 1.0


def test_parallelism_report():
    rt = RuntimeState()
    # Add some waiting tasks
    task1 = MockTask("task1", [MockLock("pool")])
    task2 = MockTask("task2", [MockLock("dataset")])
    rt.add_waiting(task1)
    rt.add_waiting(task2)
    report = rt.parallelism_report()
    assert report["waiting_tasks"] == 2
    assert report["current_max_parallel"] == rt.max_parallel
    assert isinstance(report["estimated_parallel_slots"], int)
    # Since locks are different, both could potentially run
    assert report["estimated_parallel_slots"] >= 1


def test_adaptive_parallelism_step():
    rt = RuntimeState()
    # Initially, action should be "none" because interval not reached
    step1 = rt.adaptive_parallelism_step()
    assert step1["action"] == "none"
    assert step1["reason"] == "interval_not_reached"
    # We need to simulate enough completions to reach interval.
    # Set adaptation_counter to threshold-1 and call again.
    with rt._lock:
        rt._adaptation_counter = rt._adaptation_interval - 1
    step2 = rt.adaptive_parallelism_step()
    # No throughput history yet, action likely "none"
    # but at least the method should run without error.
    assert "action" in step2
    assert "new_max_parallel" in step2


def test_load_factors():
    rt = RuntimeState()
    factors = rt.load_factors()
    expected_keys = {"waiting", "running", "completed", "failed",
                     "throughput_60s", "waiting_ratio", "locks_count",
                     "max_parallel"}
    for key in expected_keys:
        assert key in factors
    # Initially, waiting and running should be 0
    assert factors["waiting"] == 0
    assert factors["running"] == 0
    assert factors["completed"] == 0
    assert factors["failed"] == 0
    # throughput_60s should be a float
    assert isinstance(factors["throughput_60s"], float)


def test_tune_based_on_load():
    rt = RuntimeState()
    initial = rt.max_parallel
    # Add many waiting tasks to trigger increase
    for i in range(10):
        task = MockTask(f"task{i}")
        rt.add_waiting(task)
    # running is zero, waiting > 2 * running -> increase
    rt.tune_based_on_load(target_ratio=2.0)
    # Since waiting > 0 and running == 0, waiting_ratio is infinite,
    # condition waiting > target_ratio * running is True.
    # Should increase max_parallel by 1, up to limit 50.
    assert rt.max_parallel == min(initial + 1, 50)
    # Now clear waiting, add some running (mock) to test decrease
    # We cannot directly add running tasks via public API.
    # Instead, we can manually adjust waiting and running counts?
    # The method uses len(self.waiting) and len(self.running) under lock.
    # We can clear waiting and add a dummy entry to running dict.
    with rt._lock:
        rt.waiting.clear()
        rt.running["dummy"] = {"task": None, "status": "running", "started_at": 0}
    # waiting = 0, running = 1 => waiting_ratio = 0 < 2 => decrease
    rt.tune_based_on_load(target_ratio=2.0)
    # Should decrease by 1, but not below 1.
    assert rt.max_parallel == max(min(initial + 1, 50) - 1, 1)


def test_recommend_parallel():
    rt = RuntimeState()
    # No waiting tasks
    rec = rt.recommend_parallel()
    assert rec == max(1, rt.running_count)
    # Add a few tasks with no locks
    for i in range(3):
        task = MockTask(f"task{i}")
        rt.add_waiting(task)
    rec = rt.recommend_parallel()
    # Should be able to run all three (no locks), but limited by max_parallel
    assert 1 <= rec <= rt.max_parallel
    # Test aggressive mode
    rec_agg = rt.recommend_parallel(aggressive=True)
    # Aggressive may allow up to max_parallel+1 if slots available.
    # Since we have 3 tasks and max_parallel default 5, aggressive should be <= max_parallel+1.
    assert rec_agg >= rec
    assert rec_agg <= rt.max_parallel + 1


def test_parallelism_report_conflict_stats():
    rt = RuntimeState()
    # Add tasks with conflicting locks
    lock = MockLock("pool")
    task1 = MockTask("task1", [lock])
    task2 = MockTask("task2", [lock])
    rt.add_waiting(task1)
    rt.add_waiting(task2)
    report = rt.parallelism_report()
    # conflict_pairs should be 1 (pair of tasks conflict)
    assert report["conflict_pairs"] == 1
    # conflict_degree_avg should be 1.0 (each task conflicts with the other)
    assert report["conflict_degree_avg"] == 1.0
    # conflict_degree_max == 1
    assert report["conflict_degree_max"] == 1
    # conflict_degree_min == 1
    assert report["conflict_degree_min"] == 1


if __name__ == "__main__":
    pytest.main([__file__])
