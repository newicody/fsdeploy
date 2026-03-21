"""
fsdeploy.ui.screens.presets — CRUD presets de boot, 100% bus events.
"""

import os
from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Input, Label, Log, Select, Static

IS_FB = os.environ.get("TERM") == "linux"
CHECK, CROSS, WARN, ARROW, STAR = ("[OK]","[!!]","[??]","->","*") if IS_FB else ("✅","❌","⚠️","→","★")


class PresetsScreen(Screen):

    BINDINGS = [
        Binding("r", "refresh", "Rafraichir", show=True),
        Binding("n", "new_preset", "Nouveau", show=True),
        Binding("a", "activate_preset", "Activer", show=True),
        Binding("delete", "delete_preset", "Supprimer", show=True),
        Binding("enter", "next_step", "Suivant", show=True),
        Binding("escape", "app.pop_screen", "Retour", show=False),
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

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = "presets"
        self._presets: list[dict] = []
        self._selected_idx: int = -1

    @property
    def bridge(self):
        return getattr(self.app, "bridge", None)

    def compose(self) -> ComposeResult:
        yield Static("Presets de boot", id="presets-header")
        yield Static("Statut : chargement...", id="presets-status")

        with Vertical(id="presets-table-section"):
            yield Label("Presets disponibles")
            yield DataTable(id="presets-table")

        with Vertical(id="edit-section"):
            yield Label("Creer / modifier un preset")
            with Horizontal(classes="edit-row"):
                yield Label("Nom :")
                yield Input(id="input-name", placeholder="default")
            with Horizontal(classes="edit-row"):
                yield Label("Kernel :")
                yield Input(id="input-kernel", placeholder="vmlinuz-6.12.0")
            with Horizontal(classes="edit-row"):
                yield Label("Initramfs :")
                yield Input(id="input-initramfs", placeholder="initramfs-6.12.0.img")
            with Horizontal(classes="edit-row"):
                yield Label("Type init :")
                yield Select([("ZFSBootMenu","zbm"),("Minimal","minimal"),
                              ("Stream","stream"),("Custom","custom")],
                             value="zbm", id="select-init-type")
            with Horizontal(classes="edit-row"):
                yield Label("Overlay dataset :")
                yield Input(id="input-overlay", placeholder="fast_pool/overlay-system")
            with Horizontal(classes="edit-row"):
                yield Label("Rootfs SFS :")
                yield Input(id="input-rootfs", placeholder="images/rootfs.sfs")
            yield Button("Sauvegarder", variant="primary", id="btn-save")

        yield Log(id="command-log", highlight=True, auto_scroll=True)

        with Horizontal(id="action-buttons"):
            yield Button("Rafraichir", id="btn-refresh")
            yield Button("Activer", variant="primary", id="btn-activate")
            yield Button("Supprimer", variant="error", id="btn-delete")
            yield Button(f"Suivant {ARROW}", variant="success", id="btn-next")

    def on_mount(self) -> None:
        dt = self.query_one("#presets-table", DataTable)
        dt.add_columns("", "Nom", "Kernel", "Initramfs", "Type", "Overlay")
        dt.cursor_type = "row"
        self._refresh_list()

    def _refresh_list(self) -> None:
        if not self.bridge:
            return
        cfg = getattr(self.app, "config", None)
        config_path = str(getattr(cfg, "path", "")) if cfg else ""
        self.bridge.emit("preset.list", config_path=config_path,
                         callback=self._on_list)

    def _on_list(self, ticket) -> None:
        if ticket.status == "completed" and isinstance(ticket.result, list):
            self._presets = ticket.result
            self._safe_call(self._refresh_table)
            self._safe_call(lambda: self._set_status(
                f"{CHECK} {len(self._presets)} presets"))

    def _refresh_table(self) -> None:
        dt = self.query_one("#presets-table", DataTable)
        dt.clear()
        for p in self._presets:
            active = STAR if p.get("is_active") else ""
            dt.add_row(active, p.get("name","?"), p.get("kernel","?"),
                       p.get("initramfs","?"), p.get("init_type","?"),
                       p.get("overlay_dataset","—"))

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        idx = event.cursor_row
        if 0 <= idx < len(self._presets):
            self._selected_idx = idx
            p = self._presets[idx]
            self.query_one("#input-name", Input).value = p.get("name","")
            self.query_one("#input-kernel", Input).value = p.get("kernel","")
            self.query_one("#input-initramfs", Input).value = p.get("initramfs","")
            self.query_one("#input-overlay", Input).value = p.get("overlay_dataset","")
            self.query_one("#input-rootfs", Input).value = p.get("rootfs","")
            try:
                self.query_one("#select-init-type", Select).value = p.get("init_type","zbm")
            except Exception:
                pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "btn-refresh": self._refresh_list()
        elif bid == "btn-save": self._save_preset()
        elif bid == "btn-activate": self.action_activate_preset()
        elif bid == "btn-delete": self.action_delete_preset()
        elif bid == "btn-next": self.action_next_step()

    def _save_preset(self) -> None:
        if not self.bridge: return
        name = self.query_one("#input-name", Input).value.strip()
        if not name:
            self.notify("Nom requis.", severity="warning"); return
        cfg = getattr(self.app, "config", None)
        data = {
            "kernel": self.query_one("#input-kernel", Input).value.strip(),
            "initramfs": self.query_one("#input-initramfs", Input).value.strip(),
            "init_type": self.query_one("#select-init-type", Select).value,
            "overlay_dataset": self.query_one("#input-overlay", Input).value.strip(),
            "rootfs": self.query_one("#input-rootfs", Input).value.strip(),
        }
        self.bridge.emit("preset.save", name=name, data=data,
                         config_path=str(getattr(cfg,"path","")) if cfg else "",
                         callback=lambda t: self._on_saved(t, name))

    def _on_saved(self, ticket, name) -> None:
        if ticket.status == "completed":
            self._safe_log(f"{CHECK} Preset '{name}' sauvegarde")
            self._safe_call(self._refresh_list)
        else:
            self._safe_log(f"{CROSS} {ticket.error}")

    def action_activate_preset(self) -> None:
        if self._selected_idx < 0 or not self.bridge: return
        name = self._presets[self._selected_idx].get("name","")
        cfg = getattr(self.app, "config", None)
        self.bridge.emit("preset.activate", name=name,
                         config_path=str(getattr(cfg,"path","")) if cfg else "",
                         callback=lambda t: self._safe_log(
                             f"{CHECK} '{name}' active" if t.status=="completed"
                             else f"{CROSS} {t.error}"))
        self._safe_call(self._refresh_list)

    def action_delete_preset(self) -> None:
        if self._selected_idx < 0 or not self.bridge: return
        name = self._presets[self._selected_idx].get("name","")
        cfg = getattr(self.app, "config", None)
        self.bridge.emit("preset.delete", name=name,
                         config_path=str(getattr(cfg,"path","")) if cfg else "",
                         callback=lambda t: self._safe_call(self._refresh_list))

    def action_refresh(self) -> None: self._refresh_list()
    def action_new_preset(self) -> None:
        for w in ("#input-name","#input-kernel","#input-initramfs",
                  "#input-overlay","#input-rootfs"):
            self.query_one(w, Input).value = ""
        self.query_one("#input-name", Input).focus()

    def action_next_step(self) -> None:
        if hasattr(self.app, "navigate_next"): self.app.navigate_next()

    def update_from_snapshot(self, s: dict) -> None: pass
    def _log(self, m):
        try: self.query_one("#command-log", Log).write_line(m)
        except Exception: pass
    def _safe_log(self, m):
        try: self.app.call_from_thread(self._log, m)
        except Exception: self._log(m)
    def _set_status(self, t):
        try: self.query_one("#presets-status", Static).update(f"Statut : {t}")
        except Exception: pass
    def _safe_call(self, fn):
        try: self.app.call_from_thread(fn)
        except Exception: fn()
