"""
fsdeploy.scheduler.graph.task_graph
====================================
DAG de dépendances entre tasks.

Permet de définir un ordre obligatoire :
  - detect_pools → detect_datasets → mount → kernel_select → ...
"""

from collections import defaultdict, deque
from typing import Optional


class TaskGraph:
    """
    Graphe dirigé acyclique de dépendances entre types de tasks.
    Les nœuds sont des noms de task (str), pas des instances.
    """

    def __init__(self):
        self._edges: dict[str, set[str]] = defaultdict(set)     # task → {dépendances}
        self._reverse: dict[str, set[str]] = defaultdict(set)   # task → {dépendants}

    def add_dependency(self, task: str, depends_on: str) -> None:
        """task dépend de depends_on (depends_on doit s'exécuter avant task)."""
        self._edges[task].add(depends_on)
        self._reverse[depends_on].add(task)
        # Vérification immédiate de cycles
        if self._has_cycle():
            self._edges[task].discard(depends_on)
            self._reverse[depends_on].discard(task)
            raise ValueError(
                f"Cycle détecté en ajoutant {depends_on} → {task}"
            )

    def get_dependencies(self, task: str) -> set[str]:
        """Retourne les dépendances directes."""
        return set(self._edges.get(task, set()))

    def get_all_dependencies(self, task: str) -> set[str]:
        """Retourne toutes les dépendances (transitives)."""
        visited = set()
        queue = deque(self._edges.get(task, set()))
        while queue:
            dep = queue.popleft()
            if dep not in visited:
                visited.add(dep)
                queue.extend(self._edges.get(dep, set()) - visited)
        return visited

    def get_dependents(self, task: str) -> set[str]:
        """Retourne les tasks qui dépendent de task."""
        return set(self._reverse.get(task, set()))

    def can_execute(self, task: str, completed: set[str]) -> bool:
        """Vrai si toutes les dépendances de task sont dans completed."""
        deps = self._edges.get(task, set())
        return deps.issubset(completed)

    def topological_order(self) -> list[str]:
        """Retourne un ordre d'exécution valide (tri topologique)."""
        in_degree: dict[str, int] = defaultdict(int)
        all_nodes = set(self._edges.keys()) | set(self._reverse.keys())

        for task, deps in self._edges.items():
            in_degree.setdefault(task, 0)
            for dep in deps:
                in_degree[task] += 1
                in_degree.setdefault(dep, 0)

        queue = deque(n for n in all_nodes if in_degree.get(n, 0) == 0)
        result = []

        while queue:
            node = queue.popleft()
            result.append(node)
            for dependent in self._reverse.get(node, set()):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        if len(result) != len(all_nodes):
            raise ValueError("Cycle détecté dans le graphe de dépendances")

        return result

    def _has_cycle(self) -> bool:
        """Détection de cycle via DFS."""
        all_nodes = set(self._edges.keys()) | set(self._reverse.keys())
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {n: WHITE for n in all_nodes}

        def dfs(node):
            color[node] = GRAY
            for dep in self._edges.get(node, set()):
                if color.get(dep, WHITE) == GRAY:
                    return True
                if color.get(dep, WHITE) == WHITE and dfs(dep):
                    return True
            color[node] = BLACK
            return False

        return any(
            dfs(n) for n in all_nodes if color.get(n, WHITE) == WHITE
        )

    def __repr__(self) -> str:
        return f"TaskGraph({len(self._edges)} nodes)"
