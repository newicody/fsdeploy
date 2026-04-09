"""
Écran de détection avancée des partitions.
"""

from textual.app import ComposeResult
from textual.containers import Container, Vertical, Horizontal
from textual.widgets import Header, Footer, Button, Input, Select, DataTable, Static, Label
from textual.widgets.data_table import RowSelected
from textual.screen import Screen
from textual.reactive import reactive
from textual import work
from fsdeploy.lib.scheduler.bridge import SchedulerBridge

class PartitionDetectionScreen(Screen):
    """Scanner les partitions par pattern et intégrer les modules."""

    CSS = """
    PartitionDetectionScreen {
        layout: vertical;
    }
    .controls {
        height: 20%;
        padding: 1;
        border: solid $primary;
    }
    .results {
        height: 60%;
        border: solid $secondary;
    }
    .logs {
        height: 20%;
        border: solid $accent;
    }
    """

    bridge = SchedulerBridge.default()
    selected_device = reactive("")

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(classes="controls"):
            yield Static("Pattern de partition:")
            yield Input(placeholder="/dev/sd*", id="pattern")
            yield Static("Type de système de fichiers (optionnel):")
            yield Input(placeholder="vfat,ext4,...", id="fstype")
            yield Button("Scanner", id="scan")
            yield Button("Monter squashfs", id="mount-squash")
        with Container(classes="results"):
            yield DataTable(id="partitions-table")
        with Container(classes="logs"):
            yield Static(id="logs-output")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#partitions-table", DataTable)
        table.add_columns("Device", "Type", "Size", "Mountpoint", "Squashfs")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "scan":
            self.scan_partitions()
        elif event.button.id == "mount-squash":
            self.mount_squashfs()

    def on_data_table_row_selected(self, event: RowSelected) -> None:
        if event.row_key is not None:
            table = self.query_one("#partitions-table", DataTable)
            row = table.get_row(event.row_key)
            if row:
                cell_device = row[0]
                device = cell_device.value if hasattr(cell_device, 'value') else str(cell_device)
                self.selected_device = device
        else:
            self.selected_device = ""

    def scan_partitions(self):
        pattern_input = self.query_one("#pattern", Input)
        fstype_input = self.query_one("#fstype", Input)
        pattern = pattern_input.value
        fstype = fstype_input.value if fstype_input.value else None
        params = {"pattern": pattern}
        if fstype:
            params["fstype"] = fstype
        ticket = self.bridge.emit("partition.detect", params, callback=self.on_scan_result)

    def on_scan_result(self, result):
        if result and result.get("success"):
            partitions = result.get("partitions", [])
            table = self.query_one("#partitions-table", DataTable)
            table.clear()
            for part in partitions:
                table.add_row(part.get("device"), part.get("type"), part.get("size"), part.get("mountpoint"), part.get("squashfs", ""))
            logs = self.query_one("#logs-output", Static)
            logs.update(f"Scan terminé: {len(partitions)} partitions trouvées.")
        else:
            logs = self.query_one("#logs-output", Static)
            logs.update("Échec du scan.")

    def mount_squashfs(self):
        if not self.selected_device:
            self.app.notify("Aucune partition sélectionnée")
            return
        # Émettre un intent pour monter le squashfs sur l'appareil sélectionné
        ticket = self.bridge.emit("partition.squashfs.mount",
                                  {"device": self.selected_device},
                                  callback=self.on_mount_result)

    def on_mount_result(self, result):
        logs = self.query_one("#logs-output", Static)
        if result and result.get("success"):
            logs.update(f"Montage squashfs réussi sur {self.selected_device}")
        else:
            logs.update("Échec du montage squashfs")
