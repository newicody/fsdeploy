"""
fsdeploy.scheduler.core.resolver
=================================
Pipeline de résolution : sécurité → ressources → locks.

Produit un dict de résultat utilisé par le Scheduler pour décider
si une task peut être lancée immédiatement ou mise en attente.
"""

from typing import Any, Optional


class Resolver:

    def __init__(self, security_resolver=None):
        self.security_resolver = security_resolver

    def resolve(self, task, context: dict | None = None) -> dict[str, Any]:
        """
        Pipeline :
          1. Vérification sécurité (SecurityResolver)
          2. Résolution des ressources
          3. Résolution des locks

        Returns:
            {
                "allowed": bool,
                "resources": list[Resource],
                "locks": list[Lock],
                "reason": str | None
            }
        """
        context = context or {}

        # ── Sécurité ──────────────────────────────────────────────────
        if self.security_resolver:
            allowed, reason = self.security_resolver.check(task, context)
            if not allowed:
                raise PermissionError(f"Task denied: {reason}")

        # ── Ressources ────────────────────────────────────────────────
        resources = self._resolve_resources(task, context)

        # ── Locks ─────────────────────────────────────────────────────
        locks = self._resolve_locks(task, context)

        return {
            "allowed": True,
            "resources": resources,
            "locks": locks,
            "reason": None,
        }

    def _resolve_resources(self, task, context: dict) -> list:
        if hasattr(task, "required_resources"):
            return task.required_resources()
        return []

    def _resolve_locks(self, task, context: dict) -> list:
        """
        Combine les locks de la task + ceux du SecurityResolver.
        """
        locks = []

        # Locks déclarés par la task
        if hasattr(task, "required_locks"):
            locks.extend(task.required_locks())

        # Locks déduits par le SecurityResolver
        if self.security_resolver and hasattr(self.security_resolver, "resolve_locks"):
            locks.extend(self.security_resolver.resolve_locks(task))

        return locks
