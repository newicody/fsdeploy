"""
fsdeploy.ui.screens.config — Editeur de fsdeploy.conf en direct.
"""
import os
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Input, Label, Log, Select, Static

IS_FB = os.environ.get("TERM") == "linux"
CHECK, CROSS = ("[OK]","[!!]") if IS_FB else ("✅","❌")

SECTIONS = ["env","pool","partition","detection","mounts","kernel","initramfs",
            "overlay","zbm","presets","stream","network","snapshots","security",
            "scheduler","tui","log","integrity","meta"]

class ConfigScreen(Screen):
    BINDINGS = [
        Binding("s", "save_config", "Sauvegarder", show=True),
        Binding("r", "reload_config", "Recharger", show=True),
        Binding("escape", "app.pop_screen", "Retour", show=False),
    ]
    DEFAULT_CSS = """
    ConfigScreen { layout: vertical; }
    #config-header { height: auto; padding: 1 2; text-style: bold; }
    #config-status { padding: 0 2; height: 1; color: $text-muted; }
    #section-selector { height: 3; padding: 0 2; layout: horizontal; }
    #section-selector Label { width: 12; padding: 1 0; }
    #section-selector Select { width: 1fr; }
    #kv-table-section { height: 1fr; margin: 0 1; border: solid $primary; padding: 0 1; }
    #edit-row { height: 3; padding: 0 2; layout: horizontal; }
    #edit-row Label { width: 8; }
    #edit-row Input { width: 1fr; margin: 0 1; }
    #edit-row Button { margin: 0 1; }
    #command-log { height: 4; margin: 0 1; border: solid $primary-background; padding: 0 1; }
    #action-buttons { height: 3; padding: 0 2; layout: horizontal; }
    #action-buttons Button { margin: 0 1; }
    """
    def __init__(self, **kw):
        super().__init__(**kw)
        self._section = "env"; self._keys: list[tuple[str,str]] = []; self._sel = -1

    def compose(self) -> ComposeResult:
        yield Static("Configuration fsdeploy.conf", id="config-header")
        yield Static("", id="config-status")
        with Horizontal(id="section-selector"):
            yield Label("Section :")
            yield Select([(s,s) for s in SECTIONS], value="env", id="select-section")
        with Vertical(id="kv-table-section"):
            yield Label("Cles / Valeurs"); yield DataTable(id="kv-table")
        with Horizontal(id="edit-row"):
            yield Label("Cle :"); yield Input(id="input-key")
            yield Label("Val :"); yield Input(id="input-val")
            yield Button("Set", variant="primary", id="btn-set")
        yield Log(id="command-log", highlight=True, auto_scroll=True)
        with Horizontal(id="action-buttons"):
            yield Button("Sauvegarder", variant="success", id="btn-save")
            yield Button("Recharger", variant="default", id="btn-reload")

    def on_mount(self):
        dt = self.query_one("#kv-table", DataTable)
        dt.add_columns("Cle", "Valeur"); dt.cursor_type = "row"
        self._load_section()
        cfg = getattr(self.app, "config", None)
        if cfg: self._set_status(f"Config : {getattr(cfg,'path','?')}")

    def on_select_changed(self, event: Select.Changed) -> None:
        self._section = str(event.value)
        self._load_section()

    def _load_section(self):
        cfg = getattr(self.app, "config", None)
        if not cfg: return
        section = cfg.get(self._section, {})
        if isinstance(section, dict):
            self._keys = [(k, str(v)) for k, v in section.items()]
        else:
            self._keys = [(self._section, str(section))]
        self._refresh_table()

    def _refresh_table(self):
        dt = self.query_one("#kv-table", DataTable); dt.clear()
        for k, v in self._keys:
            display_v = v if len(v) < 60 else v[:57] + "..."
            dt.add_row(k, display_v)

    def on_data_table_row_selected(self, e):
        self._sel = e.cursor_row
        if 0 <= self._sel < len(self._keys):
            k, v = self._keys[self._sel]
            self.query_one("#input-key", Input).value = k
            self.query_one("#input-val", Input).value = v

    def on_button_pressed(self, e):
        bid = e.button.id or ""
        if bid == "btn-set": self._set_value()
        elif bid == "btn-save": self.action_save_config()
        elif bid == "btn-reload": self.action_reload_config()

    def _set_value(self):
        cfg = getattr(self.app, "config", None)
        if not cfg: return
        key = self.query_one("#input-key", Input).value.strip()
        val = self.query_one("#input-val", Input).value
        if not key: return
        full_key = f"{self._section}.{key}"
        cfg.set(full_key, val)
        self._log(f"  {full_key} = {val}")
        self._load_section()

    def action_save_config(self):
        cfg = getattr(self.app, "config", None)
        if not cfg: return
        try:
            cfg.save()
            self._log(f"{CHECK} Config sauvegardee")
            self.notify(f"{CHECK} Sauvegarde.", timeout=2)
        except Exception as e:
            self._log(f"{CROSS} {e}")

    def action_reload_config(self):
        cfg = getattr(self.app, "config", None)
        if not cfg: return
        try:
            cfg.reload()
            self._load_section()
            self._log(f"{CHECK} Config rechargee")
        except Exception as e:
            self._log(f"{CROSS} {e}")

    def update_from_snapshot(self, s): pass
    def _log(self, m):
        try: self.query_one("#command-log", Log).write_line(m)
        except: pass
    def _set_status(self, t):
        try: self.query_one("#config-status", Static).update(t)
        except: pass
