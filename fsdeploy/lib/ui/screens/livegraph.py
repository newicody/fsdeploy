"""
Widget de graphe temps‑réel pour le scheduler fsdeploy.

Affiche les tâches actives, leurs dépendances et les ressources sous forme
de nœuds et d'arêtes, avec animation et couleurs.
"""

import time
from typing import Dict, List, Tuple, Optional
from textual.widget import Widget
from textual.reactive import reactive


class LiveGraph(Widget):
    """
    Représentation graphique animée du graphe de tâches/resources.
    """
    DEFAULT_CSS = """
    LiveGraph {
        height: 12;
        border: solid $accent;
        background: $surface;
    }
    """

    # Données réactives
    nodes = reactive(dict)
    edges = reactive(list)
    highlight = reactive(str)

    def __init__(self, name: str | None = None, id: str | None = None,
                 classes: str | None = None) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self._last_update = 0.0
        self._animation_offset = 0.0

    def on_mount(self) -> None:
        """Démarre une mise à jour périodique."""
        self.set_interval(1.0, self._refresh_data)

    def _refresh_data(self) -> None:
        """
        Récupère les données du scheduler via le bridge.
        """
        try:
            bridge = self.app.bridge
            if hasattr(bridge, 'get_scheduler_state'):
                state = bridge.get_scheduler_state()
                self._update_from_state(state)
                return
        except Exception:
            pass
        # Données fictives pour la démo
        self.nodes = {'demo': {'label': 'demo', 'type': 'task', 'status': 'running'}}
        self.edges = []

    def _update_from_state(self, state: dict) -> None:
        """
        Extrait les nœuds et arêtes de l'état du scheduler.
        """
        nodes = {}
        # Tâches actives
        active_tasks = state.get('active_tasks', {})
        for tid, info in active_tasks.items():
            nodes[tid] = {
                'label': info.get('class', tid),
                'type': 'task',
                'status': 'running',
                'started': info.get('started', 0)
            }
        # Ressources
        resources = state.get('resources', {})
        for rpath, action in resources.items():
            nodes[rpath] = {
                'label': rpath,
                'type': 'resource',
                'status': action,
            }
        # Arêtes du DAG
        edges = []
        dag = state.get('dag', {})
        for task, deps in dag.items():
            for dep in deps:
                edges.append((dep, task))
        # Locks (ressource → owner)
        locks = state.get('active_locks', {})
        for lock_key, info in locks.items():
            parts = lock_key.split(':')
            if len(parts) >= 2:
                resource, owner = parts[0], parts[1]
                edges.append((resource, owner))

        self.nodes = nodes
        self.edges = edges

    def render(self) -> str:
        """
        Génère une représentation ASCII du graphe.
        """
        width = self.size.width
        height = self.size.height
        if width < 10 or height < 5:
            return "Graphique trop petit"

        lines = []
        lines.append("Graphe du scheduler (temps réel)")
        lines.append(f"Nœuds : {len(self.nodes)} | Arêtes : {len(self.edges)}")
        lines.append("=" * (width-2))
        # Lister les tâches actives
        active_tasks = [n for n, d in self.nodes.items() if d.get('type') == 'task']
        if active_tasks:
            lines.append("Tâches actives :")
            for tid in list(active_tasks)[:5]:
                info = self.nodes[tid]
                label = info.get('label', tid)
                lines.append(f"  [{label}] {info.get('status', '?')}")
        else:
            lines.append("Aucune tâche active")
        # Ressources
        resources = [n for n, d in self.nodes.items() if d.get('type') == 'resource']
        if resources:
            lines.append("Ressources :")
            for r in list(resources)[:3]:
                lines.append(f"  {r} → {self.nodes[r].get('status')}")
        # Arêtes importantes
        if self.edges:
            lines.append("Dépendances (exemples) :")
            for src, dst in self.edges[:4]:
                lines.append(f"  {src} → {dst}")

        # Animation
        anim = int(time.time() * 2) % 4
        dots = '.' * anim
        lines.append(f"Mise à jour{dots}")

        # Tronquer selon la hauteur disponible
        out_lines = lines[:height-2]
        return "\n".join(out_lines)

    async def on_click(self) -> None:
        """Permet de recentrer le graphe sur l'élément cliqué."""
        self.highlight = "clicked"
        self.refresh()
