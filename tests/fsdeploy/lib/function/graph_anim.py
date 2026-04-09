"""
Tâches pour fournir les données du graph animé.
"""

from fsdeploy.lib.scheduler.model.task import Task
from fsdeploy.lib.scheduler.model.intent import Intent
from fsdeploy.lib.scheduler.core.registry import register_intent

class GraphDataTask(Task):
    """Fournit les données de dépendances pour le graph."""

    def run(self):
        # Simulation: récupère l'état du scheduler
        from fsdeploy.lib.scheduler.runtime.monitor import RuntimeMonitor
        monitor = RuntimeMonitor()
        # Obtenir les tâches et dépendances
        # Pour l'instant on retourne des données fictives
        nodes = {
            "task1": {"x": 0.2, "y": 0.3, "color": "#ff0000"},
            "task2": {"x": 0.5, "y": 0.8, "color": "#00ff00"},
            "resource.pool": {"x": 0.7, "y": 0.2, "color": "#0000ff"},
        }
        edges = [
            ("task1", "task2"),
            ("task1", "resource.pool"),
        ]
        return {
            "nodes": nodes,
            "edges": edges,
            "animation_phase": 0.0
        }

@register_intent("graph.data")
class GraphDataIntent(Intent):
    """Intent pour récupérer les données du graph."""

    def build_tasks(self):
        return [GraphDataTask()]

@register_intent("graph.refresh")
class GraphRefreshIntent(Intent):
    """Intent pour rafraîchir les données du graph (alias de graph.data)."""

    def build_tasks(self):
        return [GraphDataTask()]
