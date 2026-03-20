"""
fsdeploy.scheduler.model.lock
=============================
Verrou sur une ressource pour éviter les conflits concurrents.

Un Lock est associé à un Resource et possède un propriétaire (intent_id).
Deux locks sont en conflit si leurs ressources sont en conflit.
"""

from typing import Optional

from scheduler.model.resource import Resource


class Lock:
    """Verrou sur une ressource."""

    __slots__ = ("resource", "owner_id", "exclusive")

    def __init__(self, resource: Resource | str, owner_id: str = "",
                 exclusive: bool = True):
        if isinstance(resource, str):
            resource = Resource(resource)
        self.resource = resource
        self.owner_id = owner_id
        self.exclusive = exclusive

    def conflicts(self, other: "Lock") -> bool:
        """Vrai si les deux locks sont incompatibles."""
        if not self.exclusive and not other.exclusive:
            return False  # deux locks partagés ne conflictent pas
        return self.resource.conflicts(other.resource)

    def __eq__(self, other) -> bool:
        if isinstance(other, Lock):
            return self.resource == other.resource and self.owner_id == other.owner_id
        return NotImplemented

    def __hash__(self) -> int:
        return hash((self.resource, self.owner_id))

    def __repr__(self) -> str:
        mode = "X" if self.exclusive else "S"
        return f"<Lock[{mode}] {self.resource} owner={self.owner_id}>"
