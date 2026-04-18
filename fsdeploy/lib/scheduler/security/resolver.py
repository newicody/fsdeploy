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
    SECURITY_LEVELS = ("allow", "deny", "require_sudo", "dry_run_only")

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
        Cherche la règle correspondant au security_path ou à un parent.
        Les niveaux possibles : allow, deny, require_sudo, dry_run_only.
        """
        if not self.config:
            return True, None
        try:
            security_section = self.config.get("security", {})
            rule = None
            parts = sec_path.split(".")
            for i in range(len(parts), 0, -1):
                key = ".".join(parts[:i])
                if key in security_section:
                    rule = security_section[key]
                    break
            if rule is None:
                return True, None  # pas de règle = allow

            # Normaliser
            if isinstance(rule, dict):
                level = rule.get("level", "allow")
            else:
                level = str(rule).strip().lower()

            if level == "deny":
                return False, f"Denied by config: {sec_path}"
            elif level == "require_sudo":
                if not self._check_privilege():
                    return False, f"Requires sudo: {sec_path}"
            elif level == "dry_run_only":
                dry_run = context.get("dry_run", False)
                if not dry_run:
                    return False, f"Allowed only in dry-run mode: {sec_path}"
            # "allow" ou inconnu = autorise
        except Exception:
            pass
        return True, None
