"""
GraphScreen amélioré avec animations temps réel.
"""

import math
import time
from textual.app import ComposeResult
from textual.containers import Container, ScrollableContainer
from textual.widgets import Header, Footer, Static, Button, Select
from textual.screen import Screen
from textual.reactive import reactive
from textual import work



class GraphEnhancedScreen(Screen):
    """Écran de visualisation animée des dépendances tâches-ressources."""

    CSS = """
    GraphEnhancedScreen {
        layout: horizontal;
    }
    .graph-area {
        width: 80%;
        height: 100%;
        border: solid $primary;
        overflow: hidden;
    }
    .controls {
        width: 20%;
        height: 100%;
        padding: 1;
        border-left: solid $secondary;
    }
    """

    @property
    def bridge(self):
        return getattr(self.app, "bridge", None)
    node_positions = reactive({})
    edges = reactive([])
    node_colors = reactive({})
    animation_phase = reactive(0.0)
    animation_speed = reactive(0.05)
    detail_level = reactive("medium")

    def compose(self) -> ComposeResult:
        yield Header()
        with Container():
            yield Static(id="graph-area", classes="graph-area")
            with Container(classes="controls"):
                yield Button("Rafraîchir", id="refresh")
                yield Select([("Détail bas", "low"), ("Détail moyen", "medium"), ("Détail élevé", "high")], id="detail-level", prompt="Détail")
                yield Select([("Vitesse lente", "slow"), ("Vitesse normale", "normal"), ("Vitesse rapide", "fast")], id="speed", prompt="Vitesse")
                yield Button("Centrer automatique", id="center")
        yield Footer()

    def on_mount(self) -> None:
        """Démarre la mise à jour périodique."""
        self.set_interval(0.5, self.update_animation)  # réduit de 0.1 à 0.5 s pour moins de charge CPU
        self.refresh_data()

    @work(exclusive=False)
    async def refresh_data(self) -> None:
        """Interroge le scheduler pour obtenir les données du graph."""
        ticket = self.bridge.emit("graph.refresh", callback=self.on_graph_data)
        # Le callback sera appelé plus tard

    def on_graph_data(self, result):
        """Reçoit les données du graph."""
        if result and result.get("success"):
            data = result.get("data", {})
            self.node_positions = data.get("nodes", {})
            self.edges = data.get("edges", [])
            # Initialiser les couleurs
            self.node_colors = {
                node: self._color_for_node(node, pos)
                for node, pos in self.node_positions.items()
            }
            self.update_graph_display()

    def _color_for_node(self, node, pos):
        """Retourne une couleur RGB basée sur la position et l'animation."""
        # Utiliser sinus pour créer un effet de pulsation
        r = int(127 + 127 * math.sin(self.animation_phase + pos.get('x', 0) * 2 * math.pi))
        g = int(127 + 127 * math.sin(self.animation_phase * 1.3 + pos.get('y', 0) * 2 * math.pi))
        b = int(127 + 127 * math.sin(self.animation_phase * 0.7 + (pos.get('x', 0) + pos.get('y', 0)) * 2 * math.pi))
        return (r, g, b)

    def _center_positions(self):
        """Centre les positions autour du milieu."""
        if not self.node_positions:
            return
        xs = [pos.get('x', 0) for pos in self.node_positions.values()]
        ys = [pos.get('y', 0) for pos in self.node_positions.values()]
        if not xs:
            return
        cx = sum(xs) / len(xs)
        cy = sum(ys) / len(ys)
        dx = 0.5 - cx
        dy = 0.5 - cy
        new_pos = {}
        for node, pos in self.node_positions.items():
            new_pos[node] = {
                'x': pos.get('x', 0) + dx,
                'y': pos.get('y', 0) + dy,
                **{k: v for k, v in pos.items() if k not in ('x','y')}
            }
        self.node_positions = new_pos
        self.node_colors = {
            node: self._color_for_node(node, pos)
            for node, pos in self.node_positions.items()
        }

    def update_graph_display(self):
        """Met à jour l'affichage du graph avec animation."""
        area = self.query_one("#graph-area", Static)
        if not self.node_positions:
            area.update("Aucune donnée de graph disponible.")
            return
        # Dimensions de la zone d'affichage (caractères)
        cols = 60
        rows = 20
        # Créer une grille remplie d'espaces
        grid = [[' ' for _ in range(cols)] for __ in range(rows)]
        # Mapper les coordonnées normalisées vers la grille
        node_grid_pos = {}
        for node, pos in self.node_positions.items():
            x = pos.get('x', 0)
            y = pos.get('y', 0)
            ix = int((x * (cols - 3)) + 1)
            iy = int((y * (rows - 3)) + 1)
            ix = max(0, min(cols - 1, ix))
            iy = max(0, min(rows - 1, iy))
            node_grid_pos[node] = (ix, iy)
            # Couleur
            color = self.node_colors.get(node, (255, 255, 255))
            # Caractère
            ch = '●'  # cercle plein
            # Insérer dans la grille avec code ANSI
            grid[iy][ix] = self._ansi_color(ch, color)
        # Dessiner les arêtes
        for a, b in self.edges:
            if a in node_grid_pos and b in node_grid_pos:
                x1, y1 = node_grid_pos[a]
                x2, y2 = node_grid_pos[b]
                # Ligne simple (Bresenham simplifié)
                points = self._line_points(x1, y1, x2, y2)
                for (px, py) in points:
                    if 0 <= px < cols and 0 <= py < rows:
                        if grid[py][px] == ' ':
                            grid[py][px] = self._ansi_color('·', (100, 100, 100))
        # Convertir la grille en chaîne avec codes ANSI
        lines = []
        for row in grid:
            line = ''.join(row)
            lines.append(line)
        # Ajouter une légende
        lines.append(f"\nPhase d'animation: {self.animation_phase:.2f}")
        area.update("\n".join(lines))

    def _ansi_color(self, ch, rgb):
        r, g, b = rgb
        return f"\x1b[38;2;{r};{g};{b}m{ch}\x1b[0m"

    def _line_points(self, x1, y1, x2, y2):
        """Retourne les points entiers d'une ligne approximative."""
        points = []
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        sx = 1 if x1 < x2 else -1
        sy = 1 if y1 < y2 else -1
        err = dx - dy
        while True:
            points.append((x1, y1))
            if x1 == x2 and y1 == y2:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x1 += sx
            if e2 < dx:
                err += dx
                y1 += sy
        return points

    def update_animation(self):
        """Avance l'animation."""
        self.animation_phase = (self.animation_phase + self.animation_speed) % 1.0
        # Recalculer les couleurs
        if self.node_positions:
            self.node_colors = {
                node: self._color_for_node(node, pos)
                for node, pos in self.node_positions.items()
            }
            self.update_graph_display()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "refresh":
            self.refresh_data()
        elif event.button.id == "center":
            self._center_positions()
            self.update_graph_display()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "speed":
            speeds = {"slow": 0.02, "normal": 0.05, "fast": 0.1}
            self.animation_speed = speeds.get(event.value, 0.05)
        elif event.select.id == "detail-level":
            self.detail_level = event.value
