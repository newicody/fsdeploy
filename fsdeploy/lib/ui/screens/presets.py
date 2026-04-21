"""
fsdeploy.ui.screens.presets — CRUD presets de boot, 100% bus events.
Compatible : Textual >=8.2.1 / Rich >=14.3.3
"""
import json, os
from typing import Any
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Input, Label, Log, Select, Static

IS_FB = os.environ.get("TERM") == "linux"
CHECK, CROSS, WARN, ARROW, STAR = (("[OK]","[!!]","[??]","->","*") if IS_FB else ("✅","❌","⚠️","→","★"))
# Compat Textual 5.x→8.x : Select.BLANK renomme Select.NULL
_SELECT_BLANK = getattr(Select, "NULL", getattr(Select, "BLANK", None))

class PresetsScreen(Screen):
    BINDINGS = [
        Binding("r","refresh","Rafraichir",show=True),
        Binding("n","new_preset","Nouveau",show=True),
        Binding("a","activate_preset","Activer",show=True),
        Binding("delete","delete_preset","Supprimer",show=True),
        Binding("enter","next_step","Suivant",show=True),
        Binding("escape","app.pop_screen","Retour",show=False),
    ]
    DEFAULT_CSS = """
    PresetsScreen { layout: vertical; overflow-y: auto; }
    #presets-header { height: auto; padding: 1 2; text-style: bold; }
    #presets-status { padding: 0 2; height: 1; color: $text-muted; }
    #presets-table-section { height: 1fr; margin: 0 1; border: solid $primary; padding: 0 1; }
    #edit-section { height: auto; margin: 0 1; padding: 1 2; border: solid $accent; }
    .edit-row { height: 3; layout: horizontal; }
    .edit-row Label { width: 18; padding: 1 0; }
    .edit-row Input, .edit-row Select { width: 1fr; }
    #command-log { height: 6; margin: 0 1; border: solid $primary-background; padding: 0 1; }
    #action-buttons { height: 3; padding: 0 2; layout: horizontal; }
    #action-buttons Button { margin: 0 1; }
    """
    def __init__(self, **kw):
        super().__init__(**kw); self._presets=[]; self._selected_idx=-1

    def compose(self) -> ComposeResult:
        yield Static("Presets de boot", id="presets-header")
        yield Static("Statut : chargement...", id="presets-status")
        with Vertical(id="presets-table-section"):
            dt = DataTable(id="presets-table"); dt.cursor_type = "row"
            dt.add_columns("Nom","Kernel","Initramfs","Rootfs","Actif"); yield dt
        with Vertical(id="edit-section"):
            yield Label("Editeur de preset", classes="section-title")
            with Horizontal(classes="edit-row"):
                yield Label("Nom :"); yield Input(placeholder="mon-preset", id="preset-name")
            with Horizontal(classes="edit-row"):
                yield Label("Kernel :"); yield Select([], allow_blank=True, id="preset-kernel")
            with Horizontal(classes="edit-row"):
                yield Label("Initramfs :"); yield Select([], allow_blank=True, id="preset-initramfs")
            with Horizontal(classes="edit-row"):
                yield Label("Rootfs :"); yield Input(placeholder="images/rootfs.sfs", id="preset-rootfs")
            with Horizontal(classes="edit-row"):
                yield Label("Overlay :"); yield Input(placeholder="fast_pool/overlay", id="preset-overlay")
            with Horizontal(classes="edit-row"):
                yield Label("Modules :"); yield Input(placeholder="/boot/modules", id="preset-modules")
        yield Log(id="command-log")
        with Horizontal(id="action-buttons"):
            yield Button("Sauvegarder", variant="primary", id="btn-save")
            yield Button("Dupliquer", id="btn-duplicate")
            yield Button("Supprimer", variant="error", id="btn-delete")
            yield Button(f"Suivant {ARROW}", variant="success", id="btn-next")

    def on_mount(self):
        from fsdeploy.lib.ui.bridge import SchedulerBridge
        self.bridge = SchedulerBridge.default()
        self._load_presets()

    # Textual 8.x: RowHighlighted au lieu de RowSelected
    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted):
        if event.cursor_row is not None and event.cursor_row < len(self._presets):
            self._selected_idx = event.cursor_row
            self._populate_editor(self._presets[self._selected_idx])

    def _load_presets(self):
        if not self.bridge:
            self._presets = [
                {"name":"default","kernel":"vmlinuz-6.12.0","initramfs":"initramfs-6.12.0.img",
                 "rootfs":"images/rootfs.sfs","overlay":"fast_pool/overlay","modules":"modules/6.12.0","active":True},
                {"name":"stream-only","kernel":"vmlinuz-6.12.0","initramfs":"initramfs-stream.img",
                 "rootfs":"","overlay":"","modules":"modules/6.12.0","active":False},
            ]
            self._update_table(); return
        self.bridge.emit("presets.list", callback=self._on_loaded)

    def _on_loaded(self, t):
        if t.status=="completed" and t.result: self._presets=t.result
        try: self.app.call_from_thread(self._update_table)
        except: self._update_table()

    def _update_table(self):
        try:
            dt = self.query_one("#presets-table", DataTable); dt.clear()
            for p in self._presets:
                dt.add_row(p.get("name","?"), p.get("kernel","-"), p.get("initramfs","-"),
                    p.get("rootfs","-") or "(aucun)", f"{STAR} Actif" if p.get("active") else "")
            self.query_one("#presets-status", Static).update(f"{len(self._presets)} presets")
        except: pass

    def _populate_editor(self, p):
        try:
            self.query_one("#preset-name",Input).value=p.get("name","")
            self.query_one("#preset-rootfs",Input).value=p.get("rootfs","")
            self.query_one("#preset-overlay",Input).value=p.get("overlay","")
            self.query_one("#preset-modules",Input).value=p.get("modules","")
        except: pass

    def on_button_pressed(self, e):
        bid=e.button.id or ""
        if bid=="btn-save": self._save_preset()
        elif bid=="btn-duplicate": self._duplicate()
        elif bid=="btn-delete": self.action_delete_preset()
        elif bid=="btn-next": self.action_next_step()

    def _save_preset(self):
        if self._selected_idx<0: return
        try:
            p=self._presets[self._selected_idx]
            p["name"]=self.query_one("#preset-name",Input).value or p["name"]
            p["rootfs"]=self.query_one("#preset-rootfs",Input).value
            p["overlay"]=self.query_one("#preset-overlay",Input).value
            p["modules"]=self.query_one("#preset-modules",Input).value
            ks=self.query_one("#preset-kernel",Select)
            if ks.value!=_SELECT_BLANK: p["kernel"]=str(ks.value)
            ifs=self.query_one("#preset-initramfs",Select)
            if ifs.value!=_SELECT_BLANK: p["initramfs"]=str(ifs.value)
        except: pass
        if self.bridge: self.bridge.emit("presets.save",preset=self._presets[self._selected_idx])
        self._update_table(); self._log(f"{CHECK} Preset sauvegarde")

    def _duplicate(self):
        if self._selected_idx<0: return
        o=self._presets[self._selected_idx]
        self._presets.append({**o,"name":f"{o['name']}-copy","active":False})
        self._update_table()

    def action_refresh(self): self._load_presets()
    def action_new_preset(self):
        self._presets.append({"name":f"preset-{len(self._presets)+1}","kernel":"","initramfs":"",
            "rootfs":"","overlay":"","modules":"","active":False})
        self._update_table()
    def action_activate_preset(self):
        if self._selected_idx<0: return
        for i,p in enumerate(self._presets): p["active"]=(i==self._selected_idx)
        if self.bridge: self.bridge.emit("presets.activate",name=self._presets[self._selected_idx]["name"])
        self._update_table()
    def action_delete_preset(self):
        if self._selected_idx<0: return
        self._presets.pop(self._selected_idx); self._selected_idx=-1; self._update_table()
    def action_next_step(self):
        if hasattr(self.app,"navigate_next"): self.app.navigate_next()
    def update_from_snapshot(self,s): pass
    def _log(self,m):
        try: self.query_one("#command-log",Log).write_line(m)
        except: pass
