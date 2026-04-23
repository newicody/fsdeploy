"""
fsdeploy.ui.screens.zfs_pool
=============================
Écran de gestion des pools ZFS.
Conforme à la politique Zero-OS : aucune commande système directe.
Toutes les actions sont déléguées au scheduler via bridge.emit().
"""

from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.widgets import Button, Label, DataTable, Input, Header, Footer
from textual.screen import Screen
from textual.reactive import reactive


class ZfsPoolScreen(Screen):
    """Écran de gestion des pools ZFS."""

    TITLE = "Pools ZFS"
    CSS = """
    ZfsPoolScreen {
        align: center top;
    }
    #pool-list {
        height: 60%;
        margin: 1 2;
    }
    #actions {
        height: auto;
        margin: 1 2;
    }
    Button {
        margin: 0 1;
    }
    #status {
        margin: 1 2;
        height: 3;
        background: $surface;
        color: $text;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Label("Pools ZFS détectés", id="title"),
            DataTable(id="pool-list"),
            Vertical(
                Button("Importer un pool", id="import", variant="primary"),
                Button("Exporter", id="export", variant="warning"),
                Button("Scrub", id="scrub", variant="default"),
                id="actions",
            ),
            Label("", id="status"),
        )
        yield Footer()

    def on_mount(self) -> None:
        """Initialise le tableau et lance la détection."""
        table = self.query_one("#pool-list", DataTable)
        table.add_columns("Nom", "État", "Taille", "Utilisé", "Libre")
        # Lancement asynchrone de la détection via le bridge
        self.app.bridge.emit(
            "zfs.detect",
            callback=self._on_pools_detected,
            priority=-10
        )

    def _on_pools_detected(self, ticket) -> None:
        """Callback appelé quand les pools sont détectés."""
        # Le résultat du ticket contient la liste des pools
        pools = ticket.result if ticket.result else []
        table = self.query_one("#pool-list", DataTable)
        table.clear()
        for pool in pools:
            table.add_row(
                pool.get("name", "?"),
                pool.get("state", "?"),
                pool.get("size", "?"),
                pool.get("used", "?"),
                pool.get("free", "?"),
            )
        self.query_one("#status", Label).update(f"{len(pools)} pool(s) détecté(s)")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Gère les actions utilisateur."""
        action = event.button.id
        if action == "import":
            self._import_pool()
        elif action == "export":
            self._export_pool()
        elif action == "scrub":
            self._scrub_pool()

    def _import_pool(self) -> None:
        """Importe un pool – délègue au scheduler."""
        self.query_one("#status", Label).update("Demande d'import envoyée...")
        self.app.bridge.emit(
            "zfs.import",
            pool="tank",  # exemple, à remplacer par sélection utilisateur
            callback=self._on_action_done,
        )

    def _export_pool(self) -> None:
        self.query_one("#status", Label).update("Demande d'export envoyée...")
        self.app.bridge.emit(
            "zfs.export",
            pool="tank",
            callback=self._on_action_done,
        )

    def _scrub_pool(self) -> None:
        self.query_one("#status", Label).update("Demande de scrub envoyée...")
        self.app.bridge.emit(
            "zfs.scrub",
            pool="tank",
            callback=self._on_action_done,
        )

    def _on_action_done(self, ticket) -> None:
        """Callback après une action."""
        if ticket.status == "completed":
            self.query_one("#status", Label).update("Action terminée avec succès.")
        else:
            self.query_one("#status", Label).update(f"Échec : {ticket.error}")
