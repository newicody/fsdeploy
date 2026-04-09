"""
SecurityScreen amélioré avec règles dynamiques.
"""

from textual.app import ComposeResult
from textual.containers import Container, Vertical, Horizontal
from textual.widgets import Header, Footer, DataTable, Button, Select, Input, Static
from textual.widgets.data_table import RowSelected
from textual.screen import Screen
from textual.reactive import reactive
from textual import work
from fsdeploy.lib.scheduler.bridge import SchedulerBridge

class SecurityEnhancedScreen(Screen):
    """Affiche et modifie les règles de sécurité."""

    CSS = """
    SecurityEnhancedScreen {
        layout: vertical;
    }
    .rules-table {
        height: 70%;
        border: solid $primary;
    }
    .edit-panel {
        height: 30%;
        border-top: solid $secondary;
        padding: 1;
    }
    """

    bridge = SchedulerBridge.default()
    selected_rule = reactive("")

    def compose(self) -> ComposeResult:
        yield Header()
        with Container():
            yield DataTable(id="rules-table", classes="rules-table")
            with Container(classes="edit-panel"):
                yield Static("Modifier la règle sélectionnée:")
                yield Input(placeholder="Chemin de la règle", id="rule-path")
                yield Select([("allow", "allow"), ("deny", "deny"), ("inherit", "inherit")], id="rule-action", prompt="Action")
                yield Button("Appliquer", id="apply-rule")
                yield Button("Supprimer", id="delete-rule", variant="error")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#rules-table", DataTable)
        table.add_columns("Chemin", "Action", "Source")
        self.load_rules()

    def on_data_table_row_selected(self, event: RowSelected) -> None:
        if event.row_key is not None:
            table = self.query_one("#rules-table", DataTable)
            row = table.get_row(event.row_key)
            if row:
                # row est une liste de Cell
                cell_path = row[0]
                path = cell_path.value if hasattr(cell_path, 'value') else str(cell_path)
                self.selected_rule = path
                path_input = self.query_one("#rule-path", Input)
                path_input.value = path

    @work(exclusive=False)
    async def load_rules(self) -> None:
        ticket = self.bridge.emit("security.rules.view", callback=self.on_rules_data)

    def on_rules_data(self, result):
        if result and result.get("success"):
            rules = result.get("rules", [])
            table = self.query_one("#rules-table", DataTable)
            table.clear()
            for rule in rules:
                table.add_row(rule.get("path"), rule.get("action"), rule.get("source"))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "apply-rule":
            self.modify_rule()
        elif event.button.id == "delete-rule":
            self.delete_rule()

    def modify_rule(self):
        path_input = self.query_one("#rule-path", Input)
        action_select = self.query_one("#rule-action", Select)
        path = path_input.value
        action = action_select.value
        if not path or not action:
            return
        ticket = self.bridge.emit("security.rules.modify", {"path": path, "action": action}, callback=self.on_rule_modified)

    def on_rule_modified(self, result):
        if result and result.get("success"):
            self.app.notify("Règle mise à jour")
            self.load_rules()

    def delete_rule(self):
        if not self.selected_rule:
            self.app.notify("Aucune règle sélectionnée")
            return
        ticket = self.bridge.emit("security.rules.delete",
                                  {"path": self.selected_rule},
                                  callback=self.on_rule_deleted)

    def on_rule_deleted(self, result):
        if result and result.get("success"):
            self.app.notify("Règle supprimée")
            self.load_rules()
            path_input = self.query_one("#rule-path", Input)
            path_input.value = ""
            self.selected_rule = ""
        else:
            self.app.notify("Échec de la suppression")
