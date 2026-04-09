"""
Écran Metrics : indicateurs de performance et statistiques (runtime et store).
"""

import psutil
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, Label, DataTable
from textual.binding import Binding
from textual.containers import Vertical


class MetricsScreen(Screen):
    """
    Métriques du runtime (parallelisme, utilisation mémoire, etc.)
    """

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Retour", show=True),
        Binding("r", "refresh", "Rafraîchir", show=True),
        Binding("e", "export", "Exporter", show=True),
    ]

    DEFAULT_CSS = """
    MetricsScreen {
        layout: vertical;
    }
    #metrics-title {
        text-align: center;
        width: 100%;
        padding: 1 0;
        color: $accent;
        text-style: bold;
    }
    #metrics-table {
        height: 1fr;
        border: solid $primary;
        margin: 0 1;
        padding: 0 1;
    }
    """

    def compose(self):
        yield Header()
        yield Static("Metrics", id="metrics-title")
        with Vertical():
            yield Label("Statistiques du runtime :")
            table = DataTable(id="metrics-table")
            table.add_columns("Mesure", "Valeur", "Unité")
            yield table
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_metrics()

    def refresh_metrics(self):
        """Récupère les métriques depuis le runtime et le store."""
        table = self.query_one("#metrics-table", DataTable)
        table.clear()

        # Mémoire système
        mem = psutil.virtual_memory()
        mem_used_mb = mem.used / (1024 * 1024)
        mem_total_mb = mem.total / (1024 * 1024)

        # Données du store si disponible
        store = getattr(self.app, "store", None)
        compression = "N/A"
        event_count = 0
        if store is not None:
            try:
                snapshot = store.snapshot()
                counts = snapshot.get("counts", {})
                event_count = counts.get("events", 0)
                codec = snapshot.get("codec", {})
                ratio = codec.get("ratio")
                if ratio is not None:
                    compression = f"{ratio:.1%}"
            except Exception:
                pass

        # Données du runtime (via bridge)
        bridge = getattr(self.app, "bridge", None)
        active_tasks = 0
        pending_intents = 0
        if bridge is not None:
            try:
                state = bridge.get_scheduler_state()
                active_tasks = state.get("active_tasks", 0)
                pending_intents = state.get("pending_intents", 0)
            except Exception:
                pass

        rows = [
            ("Mémoire utilisée", f"{mem_used_mb:.1f} / {mem_total_mb:.0f}", "MiB"),
            ("Tâches actives", str(active_tasks), ""),
            ("Intent en attente", str(pending_intents), ""),
            ("Events traités", str(event_count), ""),
            ("Ratio compression", compression, ""),
            ("CPU système", f"{psutil.cpu_percent():.1f}", "%"),
        ]

        for name, val, unit in rows:
            table.add_row(name, val, unit)

    def action_refresh(self):
        """Rafraîchir les métriques."""
        self.refresh_metrics()
        self.notify("Métriques rafraîchies.", timeout=2)

    def action_export(self):
        """Exporter les métriques (placeholder)."""
        self.notify("Export vers /tmp/metrics.json ...", timeout=2)
