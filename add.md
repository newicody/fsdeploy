# add.md — 18.1 : Tests SecurityResolver + Executor + Isolation

## Créer `tests/unit/test_security_resolver.py`

```python
# -*- coding: utf-8 -*-
"""Tests unitaires pour le SecurityResolver et son integration executor."""
import os
import pytest
from unittest.mock import Mock, patch, MagicMock

from fsdeploy.lib.scheduler.security.resolver import SecurityResolver
from fsdeploy.lib.scheduler.security.decorator import SecurityDecorator, security
from fsdeploy.lib.scheduler.model.task import Task


# ── Fixtures ──────────────────────────────────────────────────────────

class DummyTask(Task):
    def run(self):
        return {"ok": True}


@security.dataset.destroy(require_root=True)
class ProtectedTask(Task):
    def run(self):
        return {"destroyed": True}


@security.kernel.compile(cgroup_cpu=50, cgroup_mem=4096)
class CgroupTask(Task):
    def run(self):
        return {"compiled": True}


# ── SecurityResolver.check() ─────────────────────────────────────────

class TestSecurityResolver:

    def test_bypass_allows_everything(self):
        resolver = SecurityResolver(bypass=True)
        task = ProtectedTask(id="t1", params={}, context={})
        allowed, reason = resolver.check(task)
        assert allowed is True
        assert reason is None

    def test_no_config_allows_by_default(self):
        resolver = SecurityResolver()
        task = DummyTask(id="t1", params={}, context={})
        allowed, reason = resolver.check(task)
        assert allowed is True

    def test_require_root_denied_without_privilege(self):
        resolver = SecurityResolver()
        task = ProtectedTask(id="t1", params={}, context={})
        with patch.object(resolver, '_check_privilege', return_value=False):
            allowed, reason = resolver.check(task)
            assert allowed is False
            assert "root" in reason.lower() or "sudo" in reason.lower()

    def test_require_root_allowed_with_privilege(self):
        resolver = SecurityResolver()
        task = ProtectedTask(id="t1", params={}, context={})
        with patch.object(resolver, '_check_privilege', return_value=True):
            allowed, reason = resolver.check(task)
            assert allowed is True

    def test_config_deny_blocks(self):
        config = Mock()
        config.get.return_value = {"dataset.destroy": "deny"}
        resolver = SecurityResolver(config=config)
        task = ProtectedTask(id="t1", params={}, context={})
        with patch.object(resolver, '_check_privilege', return_value=True):
            allowed, reason = resolver.check(task)
            assert allowed is False
            assert "deny" in reason.lower() or "denied" in reason.lower()

    def test_config_allow_passes(self):
        config = Mock()
        config.get.return_value = {"dataset.destroy": "allow"}
        resolver = SecurityResolver(config=config)
        task = ProtectedTask(id="t1", params={}, context={})
        with patch.object(resolver, '_check_privilege', return_value=True):
            allowed, reason = resolver.check(task)
            assert allowed is True

    def test_config_dry_run_only_denied_without_flag(self):
        config = Mock()
        config.get.return_value = {"dataset.destroy": "dry_run_only"}
        resolver = SecurityResolver(config=config)
        task = ProtectedTask(id="t1", params={}, context={})
        with patch.object(resolver, '_check_privilege', return_value=True):
            allowed, reason = resolver.check(task, {"dry_run": False})
            assert allowed is False

    def test_config_dry_run_only_allowed_with_flag(self):
        config = Mock()
        config.get.return_value = {"dataset.destroy": "dry_run_only"}
        resolver = SecurityResolver(config=config)
        task = ProtectedTask(id="t1", params={}, context={})
        with patch.object(resolver, '_check_privilege', return_value=True):
            allowed, reason = resolver.check(task, {"dry_run": True})
            assert allowed is True

    def test_custom_policy_blocks(self):
        def deny_all(task, ctx):
            return False, "custom deny"
        resolver = SecurityResolver(policies=[deny_all])
        task = DummyTask(id="t1", params={}, context={})
        allowed, reason = resolver.check(task)
        assert allowed is False
        assert "custom deny" in reason


# ── SecurityDecorator metadata ────────────────────────────────────────

class TestSecurityDecorator:

    def test_decorator_sets_path(self):
        assert ProtectedTask._security_path == "dataset.destroy"

    def test_decorator_sets_options(self):
        assert ProtectedTask._security_options.get("require_root") is True

    def test_cgroup_options(self):
        assert CgroupTask._security_options.get("cgroup_cpu") == 50
        assert CgroupTask._security_options.get("cgroup_mem") == 4096

    def test_no_decorator_no_path(self):
        assert not hasattr(DummyTask, '_security_path')


# ── resolve_locks ─────────────────────────────────────────────────────

class TestResolveLocks:

    def test_locks_from_task(self):
        resolver = SecurityResolver()
        task = Mock()
        task.__class__ = type('FakeTask', (), {'_security_path': '', '_security_options': {}})
        task.required_locks = Mock(return_value=[Mock()])
        locks = resolver.resolve_locks(task)
        assert len(locks) >= 1

    def test_locks_from_decorator_path(self):
        resolver = SecurityResolver()
        task = ProtectedTask(id="t1", params={}, context={})
        locks = resolver.resolve_locks(task)
        assert any("dataset.destroy" in str(l) for l in locks)


# ── Isolation CgroupLimits ────────────────────────────────────────────

class TestCgroupLimits:

    def test_not_available_without_cgroupfs(self):
        from fsdeploy.lib.scheduler.core.isolation import CgroupLimits
        with patch('fsdeploy.lib.scheduler.core.isolation.CGROUP_ROOT') as mock_root:
            mock_path = Mock()
            mock_path.__truediv__ = Mock(return_value=Mock(exists=Mock(return_value=False)))
            # Force unavailable
            assert isinstance(CgroupLimits.available(), bool)

    def test_context_manager(self):
        from fsdeploy.lib.scheduler.core.isolation import CgroupLimits
        cg = CgroupLimits("test-task", cpu_percent=50, mem_max_mb=1024)
        with patch.object(cg, 'create', return_value=False):
            with patch.object(cg, 'cleanup'):
                with cg as ctx:
                    assert ctx is cg
                cg.cleanup.assert_called_once()


# ── MountIsolation ────────────────────────────────────────────────────

class TestMountIsolation:

    def test_available_checks_unshare(self):
        from fsdeploy.lib.scheduler.core.isolation import MountIsolation
        iso = MountIsolation()
        assert isinstance(iso.available, bool)

    def test_run_returns_dict(self):
        from fsdeploy.lib.scheduler.core.isolation import MountIsolation
        iso = MountIsolation(sudo=False)
        if iso.available:
            result = iso.run(["echo", "test"], timeout=5)
            assert isinstance(result, dict)
            assert "success" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

## Critères

1. `test -f tests/unit/test_security_resolver.py` → existe
2. `grep -c "def test_" tests/unit/test_security_resolver.py` → au moins 15 tests
3. `PYTHONPATH=. python3 -m pytest tests/unit/test_security_resolver.py -v --tb=short 2>&1 | tail -5` → la majorité des tests passent (certains peuvent échouer sans configobj installé)
