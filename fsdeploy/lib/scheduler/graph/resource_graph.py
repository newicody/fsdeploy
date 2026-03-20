"""
fsdeploy.scheduler.graph.resource_graph
========================================
Graphe des ressources et de leurs relations de conflit.

Utilisé pour visualiser les zones de conflit et optimiser le parallélisme.
"""

from collections import defaultdict
from typing import Optional

from scheduler.model.resource import Resource


class ResourceGraph:
    """
    Graphe des ressources avec suivi de propriété.
    """

    def __init__(self):
        self._resources: dict[str, Resource] = {}       # id → Resource
        self._owners: dict[str, set[str]] = defaultdict(set)  # resource_id → {task_ids}

    def register(self, resource: Resource) -> None:
        """Enregistre une ressource."""
        self._resources[resource.id] = resource

    def acquire(self, resource: Resource, task_id: str) -> None:
        """Marque une ressource comme utilisée par une task."""
        self.register(resource)
        self._owners[resource.id].add(task_id)

    def release(self, resource: Resource, task_id: str) -> None:
        """Libère la ressource pour une task."""
        self._owners[resource.id].discard(task_id)
        if not self._owners[resource.id]:
            del self._owners[resource.id]

    def is_available(self, resource: Resource) -> bool:
        """Vrai si la ressource n'est utilisée par personne."""
        # Vérifier aussi les parents et enfants
        for rid, owners in self._owners.items():
            if not owners:
                continue
            existing = self._resources.get(rid)
            if existing and existing.conflicts(resource):
                return False
        return True

    def get_owners(self, resource: Resource) -> set[str]:
        """Retourne les IDs des tasks qui utilisent cette ressource."""
        return set(self._owners.get(resource.id, set()))

    def get_conflicts(self, resource: Resource) -> list[Resource]:
        """Liste les ressources en conflit avec resource."""
        conflicts = []
        for rid, res in self._resources.items():
            if res != resource and res.conflicts(resource):
                if self._owners.get(rid):
                    conflicts.append(res)
        return conflicts

    @property
    def active_resources(self) -> dict[str, set[str]]:
        """Ressources actuellement acquises."""
        return {k: v for k, v in self._owners.items() if v}

    def __repr__(self) -> str:
        active = len(self.active_resources)
        total = len(self._resources)
        return f"ResourceGraph(total={total}, active={active})"
