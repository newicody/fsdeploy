"""
Écran de tableau de bord de monitoring.
Affiche les métriques d'exécution des tâches en temps réel.
"""

from textual.screen import Screen
from textual.app import ComposeResult
from textual.widgets import Header, Footer, Static, DataTable
from textual.containers import Container
from datetime import datetime
import time
from ...scheduler.metrics import get_task_metrics, get_performance_stats

class MonitoringScreen(Screen):
    """
    Écran principal pour le monitoring des tâches.
    """

    BINDINGS = [
        ("r", "refresh", "Rafraîchir"),
        ("escape", "app.pop_screen", "Quitter"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        stats_container = Container(
            Static(id="stats_text"),
            id="stats_container",
        )
        yield stats_container
        yield Container(
            Static("Tableau de bord de monitoring - Métriques des tâches", id="title"),
            DataTable(id="metrics_table"),
            id="monitoring_container",
        )
        yield Footer()

    def on_mount(self) -> None:
        self._update_table()
        self._update_stats()
        # Rafraîchissement périodique toutes les 5 secondes
        self.set_interval(5, self._update_table)
        self.set_interval(5, self._update_stats)

    def _update_table(self) -> None:
        """Met à jour le tableau avec les métriques actuelles."""
        table = self.query_one("#metrics_table", DataTable)
        table.clear()
        table.add_columns("ID Tâche", "État", "Début", "Durée", "Ressources")
        for task in get_task_metrics():
            start_str = time.strftime("%H:%M:%S", time.localtime(task["start_time"]))
            duration_str = f"{task['duration']:.1f}s"
            resource = task["resource"] or ""
            table.add_row(
                task["id"],
                task["state"],
                start_str,
                duration_str,
                resource,
            )

    def action_refresh(self) -> None:
        """Rafraîchir les données."""
        self._update_table()
        self._update_stats()
        self.notify("Données de monitoring rafraîchies")

    def _update_stats(self) -> None:
        """Met à jour le widget des statistiques de performance."""
        stats = get_performance_stats()
        text = (
            f"Durée moyenne tâche: {stats['avg_task_duration']:.2f}s | "
            f"Tâches/min: {stats['tasks_per_minute']:.1f} | "
            f"Taille file attente: {stats['queue_length']} | "
            f"Uptime: {stats['uptime_hours']:.1f}h"
        )
        self.query_one("#stats_text", Static).update(text)
