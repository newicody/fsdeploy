"""
Écran de gestion des snapshots de configuration.
"""

from datetime import datetime
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, DataTable, Label, Button
from textual.containers import Container, VerticalScroll, Horizontal
from textual.binding import Binding
from textual.reactive import reactive
from textual import on

from fsdeploy.lib.intents.config_intent import (
    ConfigSnapshotListIntent,
    ConfigSnapshotSaveIntent,
    ConfigSnapshotRestoreIntent,
)


class ConfigSnapshotScreen(Screen):
    """
    Affiche et gère les snapshots de configuration.
    """

    BINDINGS = [
        ("escape", "app.pop_screen", "Retour"),
        ("r", "refresh", "Rafraîchir"),
        ("s", "save", "Sauvegarder"),
    ]

    DEFAULT_CSS = """
    ConfigSnapshotScreen {
        layout: vertical;
    }

    #title {
        height: auto;
        padding: 1 2;
        text-style: bold;
        background: $boost;
    }

    #snapshot-table {
        height: 1fr;
        border: solid $accent;
    }

    #button-bar {
        height: auto;
        padding: 1 2;
        border-top: solid $panel;
    }

    #status {
        height: 1;
        padding: 0 2;
        color: $text-muted;
    }
    """

    snapshots = reactive(list)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._selected = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield VerticalScroll(
            Label("Snapshots de configuration", id="title"),
            DataTable(id="snapshot-table"),
            Horizontal(
                Button("Rafraîchir", variant="primary", id="refresh"),
                Button("Sauvegarder", variant="success", id="save"),
                Button("Restaurer", variant="warning", id="restore"),
                Button("Retour", variant="default", id="back"),
                id="button-bar",
            ),
            Label("", id="status"),
        )
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#snapshot-table", DataTable)
        table.add_columns("Nom", "Date", "Taille", "Chemin")
        self.refresh_snapshots()

    def refresh_snapshots(self) -> None:
        """Met à jour la liste des snapshots via l'intent."""
        # Pour l'instant, on utilise la tâche directement via l'intent.
        # Nous allons simuler l'appel, car l'intent doit être exécuté par le scheduler.
        # Pour simplifier, on va appeler la tâche directement depuis le store compressé
        # ou bien on va lire le répertoire des snapshots.
        # Implémentation simplifiée : lire le dossier ~/.config/fsdeploy/snapshots/
        import os
        from pathlib import Path
        config_dir = Path.home() / ".config" / "fsdeploy"
        snapshots_dir = config_dir / "snapshots"
        snapshots = []
        if snapshots_dir.exists():
            for f in snapshots_dir.glob("*.conf"):
                stat = f.stat()
                snapshots.append({
                    "name": f.stem,
                    "path": str(f),
                    "size": stat.st_size,
                    "mtime": stat.st_mtime,
                })
        self.snapshots = snapshots
        self.update_table()

    def update_table(self) -> None:
        table = self.query_one("#snapshot-table", DataTable)
        table.clear()
        for snap in self.snapshots:
            dt = datetime.fromtimestamp(snap["mtime"]).strftime("%Y-%m-%d %H:%M")
            size_kb = snap["size"] / 1024.0
            table.add_row(
                snap["name"],
                dt,
                f"{size_kb:.1f} KiB",
                snap["path"],
            )
        self.update_status(f"{len(self.snapshots)} snapshot(s)")

    def update_status(self, message: str) -> None:
        self.query_one("#status", Label).update(message)

    @on(Button.Pressed, "#refresh")
    def handle_refresh(self) -> None:
        self.refresh_snapshots()
        self.notify("Liste rafraîchie", severity="information")

    @on(Button.Pressed, "#save")
    def handle_save(self) -> None:
        # Demander un nom via un prompt (simplifié : nom par défaut)
        from textual.dialog import InputDialog
        def on_save(name: str) -> None:
            if not name:
                return
            # Créer un intent de sauvegarde
            intent = ConfigSnapshotSaveIntent(
                params={"name": name, "description": "Sauvegarde depuis UI"}
            )
            # Dans une vraie implémentation, on lancerait l'intent via le bridge.
            # Pour l'instant, on exécute la tâche directement.
            from fsdeploy.lib.function.config.snapshot import ConfigSnapshotTask
            task = ConfigSnapshotTask(
                id=f"ui_save_{name}",
                params={"action": "save", "name": name},
                context={"source": "ui"},
            )
            result = task.run()
            if "error" in result:
                self.notify(f"Erreur : {result['error']}", severity="error")
            else:
                self.notify(f"Snapshot '{name}' sauvegardé", severity="success")
                self.refresh_snapshots()
        # Pour l'instant, on utilise un nom généré
        import time
        name = f"snap_{int(time.time())}"
        on_save(name)

    @on(Button.Pressed, "#restore")
    def handle_restore(self) -> None:
        table = self.query_one("#snapshot-table", DataTable)
        if not table.cursor_row:
            self.notify("Aucun snapshot sélectionné", severity="warning")
            return
        idx = table.cursor_row
        if idx >= len(self.snapshots):
            return
        snap = self.snapshots[idx]
        name = snap["name"]
        # Confirmation
        def do_restore() -> None:
            from fsdeploy.lib.function.config.snapshot import ConfigSnapshotTask
            task = ConfigSnapshotTask(
                id=f"ui_restore_{name}",
                params={"action": "restore", "name": name},
                context={"source": "ui"},
            )
            result = task.run()
            if "error" in result:
                self.notify(f"Erreur : {result['error']}", severity="error")
            else:
                self.notify(f"Configuration restaurée depuis '{name}'", severity="success")
        do_restore()

    @on(Button.Pressed, "#back")
    def handle_back(self) -> None:
        self.app.pop_screen()

    def action_refresh(self) -> None:
        self.handle_refresh()

    def action_save(self) -> None:
        self.handle_save()
