class Resolver:

    def __init__(self, security_resolver=None):
        self.security_resolver = security_resolver

    # -------------------------
    # ENTRY POINT
    # -------------------------
    def resolve(self, task, context=None):
        """
        Pipeline de résolution :
        1. sécurité (delegated)
        2. ressources
        """

        context = context or {}

        # -------------------------
        # SECURITY (delegation)
        # -------------------------
        if self.security_resolver:
            allowed, reason = self.security_resolver.check(task, context)

            if not allowed:
                raise PermissionError(f"Task denied: {reason}")

        # -------------------------
        # RESOURCES
        # -------------------------
        resources = self._resolve_resources(task, context)

        return {
            "allowed": True,
            "resources": resources,
            "reason": None
        }

    # -------------------------
    # RESOURCE RESOLUTION
    # -------------------------
    def _resolve_resources(self, task, context):

        if hasattr(task, "required_resources"):
            return task.required_resources()

        return []
