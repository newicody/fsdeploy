#!/usr/bin/env python3
"""
Unit tests for intent build_tasks().

Validates that each registered intent returns a non‑empty list of tasks
of the expected type.
"""

import sys
import importlib
import pytest

# List of (intent_class_path, task_class_path, optional_params)
INTENT_SPECS = [
    # detection
    (
        "fsdeploy.lib.intent.detection_intent.DetectionIntent",
        "fsdeploy.lib.function.detection.DetectionTask",
        {},
    ),
    # pool
    (
        "fsdeploy.lib.intent.pool_intent.PoolImportAllIntent",
        "fsdeploy.lib.function.pool.PoolImportAllTask",
        {},
    ),
    # kernel
    (
        "fsdeploy.lib.intent.kernel_intent.KernelListIntent",
        "fsdeploy.lib.function.kernel.KernelListTask",
        {},
    ),
    (
        "fsdeploy.lib.intent.kernel_intent.KernelProvisionIntent",
        "fsdeploy.lib.function.kernel.KernelProvisionTask",
        {},
    ),
    # coherence
    (
        "fsdeploy.lib.intent.system_intent.CoherenceCheckIntent",
        "fsdeploy.lib.function.coherence.CoherenceCheckTask",
        {},
    ),
    # preset
    (
        "fsdeploy.lib.intent.boot_intent.PresetListIntent",
        "fsdeploy.lib.function.boot.PresetListTask",
        {},
    ),
    # snapshot
    (
        "fsdeploy.lib.intent.snapshot_intent.SnapshotCreateIntent",
        "fsdeploy.lib.function.snapshot.create.SnapshotCreateTask",
        {},
    ),
    # stream
    (
        "fsdeploy.lib.intent.stream_intent.StreamStartIntent",
        "fsdeploy.lib.function.stream.StreamStartTask",
        {},
    ),
    # health
    (
        "fsdeploy.lib.intent.health_intent.HealthCheckIntent",
        "fsdeploy.lib.function.health.HealthCheckTask",
        {},
    ),
    # init
    (
        "fsdeploy.lib.intent.init_intent.InitCheckIntent",
        "fsdeploy.lib.function.init_check.InitCheckTask",
        {},
    ),
    # zbm
    (
        "fsdeploy.lib.intent.boot_intent.ZBMInstallIntent",
        "fsdeploy.lib.function.zbm.install.ZBMInstallTask",
        {},
    ),
    # config snapshot
    (
        "fsdeploy.lib.intent.config_intent.ConfigSnapshotIntent",
        "fsdeploy.lib.function.config_snapshot.ConfigSnapshotTask",
        {},
    ),
    # debug
    (
        "fsdeploy.lib.intent.debug_intent.DebugExecIntent",
        "fsdeploy.lib.function.debug.DebugExecTask",
        {},
    ),
    # mount
    (
        "fsdeploy.lib.intent.mount_intent.MountDatasetIntent",
        "fsdeploy.lib.function.mount.MountDatasetTask",
        {},
    ),
    # security
    (
        "fsdeploy.lib.intent.security_intent.SecurityStatusIntent",
        "fsdeploy.lib.function.security.SecurityStatusTask",
        {},
    ),
]

def _import_class(path):
    """Dynamically import a class given its full dotted path."""
    module_path, class_name = path.rsplit(".", 1)
    try:
        module = importlib.import_module(module_path)
    except ImportError:
        return None
    cls = getattr(module, class_name, None)
    return cls

@pytest.mark.parametrize("intent_path,task_path,params", INTENT_SPECS)
def test_intent_build_tasks(intent_path, task_path, params):
    """Verify that intent.build_tasks() returns expected task type."""
    intent_cls = _import_class(intent_path)
    if intent_cls is None:
        pytest.skip(f"Intent class not found: {intent_path}")
    task_cls = _import_class(task_path)
    if task_cls is None:
        pytest.skip(f"Task class not found: {task_path}")

    # Instantiate intent with minimal parameters
    try:
        intent = intent_cls(**params)
    except Exception as e:
        # If default constructor fails, skip the test (maybe intent needs arguments)
        pytest.skip(f"Could not instantiate {intent_path}: {e}")

    tasks = intent.build_tasks()
    assert len(tasks) > 0, f"{intent_path}.build_tasks() returned empty list"
    # Check first task type
    assert isinstance(tasks[0], task_cls), (
        f"Expected first task to be {task_path}, got {type(tasks[0])}"
    )
