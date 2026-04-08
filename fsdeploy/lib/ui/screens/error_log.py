"""
Écran de journal des erreurs pour afficher les échecs d'intents.
"""

from datetime import datetime
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, DataTable, Label
from textual.containers import Container, VerticalScroll

from fsdeploy.lib.scheduler.intentlog.log import intent_log


class ErrorLogScreen(Screen):
    """
    Affiche la liste des intents qui ont échoué.
    """

    BINDINGS = [("escape", "app.pop_screen", "Retour")]

    DEFAULT_CSS = """
    ErrorLogScreen {
        layout: vertical;
    }

    #error-title {
        height: auto;
        padding: 1 2;
        text-style: bold;
        background: $boost;
    }

    #error-table {
        height: 1fr;
        border: solid $accent;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        yield VerticalScroll(
            Label("Journal des erreurs (intents échoués)", id="error-title"),
            DataTable(id="error-table"),
        )
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#error-table", DataTable)
        table.add_columns("ID", "Classe", "Message", "Heure", "Contexte")
        failures = intent_log.get_failures(limit=100)
        for entry in failures:
            ts = entry.get("timestamp", 0)
            dt = ""
            if ts:
                try:
                    dt = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
                except (ValueError, OSError):
                    dt = str(ts)
            # Extraire un aperçu du contexte
            ctx = entry.get("context")
            ctx_preview = ""
            if ctx:
                # Prendre les deux premières clés
                parts = [f"{k[:10]}:{str(v)[:10]}" for k, v in list(ctx.items())[:2]]
                ctx_preview = ",".join(parts)
                if len(ctx) > 2:
                    ctx_preview += "…"
            table.add_row(
                entry.get("id", "?"),
                entry.get("class", "?"),
                (entry.get("error") or "")[:60],
                dt,
                ctx_preview,
            )

    def action_app_pop_screen(self) -> None:
        self.app.pop_screen()
