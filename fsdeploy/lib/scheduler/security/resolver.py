"""
fsdeploy.scheduler.security.resolver
=====================================
Transforme les métadonnées des décorateurs en règles effectives.

Combine : decorator metadata + configobj → ressources, locks, contraintes.
"""

from typing import Any, Callable, Optional

from scheduler.model.resource import Resource
from scheduler.model.lock import Lock


class SecurityResolver:
    """
    Vérifie les droits et produit les locks/ressources pour une task.
    """

    def __init__(self, policies: list[Callable] | None = None,
                 config: Any = None, bypass: bool = False):
        self.policies = policies or []
        self.config = config
        self.bypass = bypass

    # ── Entry point ───────────────────────────────────────────────────────────

    def check(self, task, context: dict | None = None) -> tuple[bool, str | None]:
        """
        Vérifie si la task est autorisée.
        Returns: (allowed, reason)
        """
        if self.bypass:
            return True, None

        context = context or {}

        # 1. Role check basique
        required_role = getattr(task, "required_role", None)
        user_role = context.get("role")
        if required_role and user_role != required_role:
            return False, f"Role '{user_role}' not allowed (requires '{required_role}')"

        # 2. Security path check (depuis le décorateur)
        sec_path = getattr(task.__class__, "_security_path", "")
        sec_opts = getattr(task.__class__, "_security_options", {})

        if sec_opts.get("require_root"):
            if not self._check_privilege():
                return False, f"Task {task} requires root/sudo privilege"

        # 3. Config-based rules
        if sec_path and self.config:
            allowed, reason = self._check_config_rules(sec_path, task, context)
            if not allowed:
                return False, reason

        # 4. Custom policies
        for policy in self.policies:
            try:
                allowed, reason = policy(task, context)
                if not allowed:
                    return False, reason
            except Exception as e:
                return False, f"Policy error: {e}"

        return True, None

    def resolve_locks(self, task) -> list[Lock]:
        """
        Produit les locks nécessaires pour une task.
        Combine les locks déclarés par la task + ceux déduits du security path.
        """
        locks = []

        # Locks déclarés par la task
        if hasattr(task, "required_locks"):
            locks.extend(task.required_locks())

        # Locks déduits du decorator path
        sec_path = getattr(task.__class__, "_security_path", "")
        sec_opts = getattr(task.__class__, "_security_options", {})

        if sec_path and sec_opts.get("exclusive", True):
            resource = Resource(sec_path)
            owner = getattr(task, "id", "unknown")
            locks.append(Lock(resource, owner_id=str(owner)))

        return locks

    def resolve_resources(self, task) -> list[Resource]:
        """
        Produit les ressources nécessaires.
        """
        resources = []
        if hasattr(task, "required_resources"):
            resources.extend(task.required_resources())
        return resources

    # ── Internal ──────────────────────────────────────────────────────────────

    def _check_privilege(self) -> bool:
        """Vérifie si on a les droits root/sudo."""
        import os
        import subprocess

        if os.geteuid() == 0:
            return True
        try:
            result = subprocess.run(
                ["sudo", "-n", "true"],
                capture_output=True, timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False

    def _check_config_rules(self, sec_path: str, task, context: dict) -> tuple[bool, str | None]:
        """
        Vérifie les règles dans configobj.
        Section [security] avec des clés comme :
            dataset.snapshot.allowed = true
            dataset.destroy.require_confirm = true
        """
        if not self.config:
            return True, None

        try:
            security_section = self.config.get("security", {})
            rule = security_section.get(sec_path, {})

            if isinstance(rule, dict):
                if rule.get("allowed") == "false":
                    return False, f"Disabled by config: {sec_path}"
                if rule.get("require_confirm") == "true":
                    # La confirmation est gérée par la TUI, pas ici
                    pass

            elif isinstance(rule, str):
                if rule == "false" or rule == "deny":
                    return False, f"Denied by config: {sec_path}"

        except Exception:
            pass

        return True, None
