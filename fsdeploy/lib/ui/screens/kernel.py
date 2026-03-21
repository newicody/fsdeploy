"""
fsdeploy.ui.screens.kernel
============================
Ecran de gestion des noyaux — 100% bus events.

Operations :
  bridge.emit("kernel.list", boot_path="/mnt/boot")
  bridge.emit("kernel.switch", version="6.12.0", boot_path="/mnt/boot")
  bridge.emit("kernel.install", source="/path/to.deb", boot_path="/mnt/boot")
  bridge.emit("kernel.compile", source_dir="/usr/src/linux", jobs=8)

Affiche :
  - Liste des kernels disponibles (version, taille, actif, initramfs, modules)
  - Kernel actif en surbrillance
  - Actions : switch, installer depuis .deb, compiler depuis source
  - Log des commandes executees par le scheduler
"""

import os
from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import (
    Button, DataTable, Input, Label, Log, Rule, Static,
)


IS_FB = os.environ.get("TERM") == "linux"
CHECK = "[OK]" if IS_FB else "✅"
CROSS = "[!!]" if IS_FB else "❌"
WARN  = "[??]" if IS_FB else "⚠️"
ARROW = "->" if IS_FB else "→"
STAR  = "*" if IS_FB else "★"


class KernelScreen(Screen):

    BINDINGS = [
        Binding("r", "refresh", "Rafraichir", show=True),
        Binding("s", "switch_kernel", "Activer", show=True),
        Binding("i", "install_kernel", "Installer .deb", show=True),
        Binding("c", "compile_kernel", "Compiler", show=True),
        Binding("enter", "next_step", "Suivant", show=True),
        Binding("escape", "app.pop_screen", "Retour", show=False),
    ]

    DEFAULT_CSS = """
    KernelScreen { layout: vertical; }
    #kernel-header { height: auto; padding: 1 2; text-style: bold; }
    #kernel-status { padding: 0 2; height: 1; color: $text-muted; }
    #active-kernel { height: auto; padding: 1 2; border: solid $success;
                     margin: 0 1; }
    #kernel-table-container { height: 1fr; margin: 0 1;
                              border: solid $primary; padding: 0 1; }
    #install-row { height: 3; padding: 0 2; layout: horizontal; }
    #install-row Input { width: 1fr; margin: 0 1; }
    #install-row Button { margin: 0 1; }
    #command-log { height: 8; margin: 0 1; border: solid $primary-background;
                   padding: 0 1; }
    #action-buttons { height: 3; padding: 0 2; layout: horizontal; }
    #action-buttons Button { margin: 0 1; }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = "kernel"
        self._kernels: list[dict] = []
        self._selected_idx: int = -1
        self._boot_path: str = "/boot"

    @property
    def bridge(self):
        return getattr(self.app, "bridge", None)

    # ── Compose ─────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Static("Gestion des noyaux", id="kernel-header")
        yield Static("Statut : chargement...", id="kernel-status")

        with Vertical(id="active-kernel"):
            yield Label("Kernel actif", classes="info-label")
            yield Label("aucun", id="active-kernel-detail")

        with Vertical(id="kernel-table-container"):
            yield Label("Noyaux disponibles")
            yield DataTable(id="kernel-table")

        with Horizontal(id="install-row"):
            yield Label("Source :")
            yield Input(placeholder="/chemin/vers/linux-image.deb ou /usr/src/linux",
                        id="source-input")
            yield Button("Installer", variant="primary", id="btn-install")
            yield Button("Compiler", variant="warning", id="btn-compile")

        yield Log(id="command-log", highlight=True, auto_scroll=True)

        with Horizontal(id="action-buttons"):
            yield Button("Rafraichir", variant="default", id="btn-refresh")
            yield Button(f"Activer le selectionne {ARROW}", variant="primary",
                         id="btn-switch")
            yield Button(f"Suivant {ARROW}", variant="success", id="btn-next")

    def on_mount(self) -> None:
        dt = self.query_one("#kernel-table", DataTable)
        dt.add_columns("", "Version", "Fichier", "Taille",
                        "Initramfs", "Modules")
        dt.cursor_type = "row"

        # Charger boot_path depuis la config
        cfg = getattr(self.app, "config", None)
        if cfg:
            bp = cfg.get("pool.boot_mount", "")
            if bp:
                self._boot_path = bp

        self._refresh_list()

    # ── Rafraichir la liste ─────────────────────────────────────────

    def _refresh_list(self) -> None:
        if not self.bridge:
            return
        self.bridge.emit("kernel.list",
                         boot_path=self._boot_path,
                         callback=self._on_kernel_list)
        self._log(f"  -> kernel.list({self._boot_path})")

    def _on_kernel_list(self, ticket) -> None:
        if ticket.status == "completed" and isinstance(ticket.result, list):
            self._kernels = ticket.result
            self._safe_call(self._refresh_table)
            n = len(self._kernels)
            active = next((k for k in self._kernels if k.get("active")), None)
            if active:
                self._safe_call(lambda: self._set_active_label(active))
            self._safe_call(lambda: self._set_status(
                f"{CHECK} {n} noyaux trouves"))
        elif ticket.status == "failed":
            self._safe_call(lambda: self._set_status(
                f"{CROSS} Erreur : {ticket.error}"))

    def _refresh_table(self) -> None:
        dt = self.query_one("#kernel-table", DataTable)
        dt.clear()
        for k in self._kernels:
            active = STAR if k.get("active") else ""
            size_mb = k.get("size", 0) / (1024 * 1024)
            modules = CHECK if k.get("has_modules") else "-"
            initramfs = k.get("initramfs", "") or "-"
            dt.add_row(
                active,
                k.get("version", "?"),
                k.get("file", "?"),
                f"{size_mb:.1f} MB",
                initramfs,
                modules,
            )

    def _set_active_label(self, kernel: dict) -> None:
        version = kernel.get("version", "?")
        initramfs = kernel.get("initramfs", "aucun")
        modules = "oui" if kernel.get("has_modules") else "non"
        self.query_one("#active-kernel-detail", Label).update(
            f"vmlinuz-{version}   initramfs={initramfs}   modules={modules}")

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self._selected_idx = event.cursor_row

    # ── Actions ─────────────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "btn-refresh":
            self._refresh_list()
        elif bid == "btn-switch":
            self.action_switch_kernel()
        elif bid == "btn-install":
            self.action_install_kernel()
        elif bid == "btn-compile":
            self.action_compile_kernel()
        elif bid == "btn-next":
            self.action_next_step()

    def action_refresh(self) -> None:
        self._refresh_list()

    def action_switch_kernel(self) -> None:
        """Active le kernel selectionne via le bus."""
        if self._selected_idx < 0 or self._selected_idx >= len(self._kernels):
            self.notify("Selectionnez un kernel.", severity="warning")
            return
        if not self.bridge:
            return

        kernel = self._kernels[self._selected_idx]
        version = kernel.get("version", "")
        if not version:
            return

        self.bridge.emit("kernel.switch",
                         version=version,
                         boot_path=self._boot_path,
                         callback=self._on_switch_done)
        self._log(f"  -> kernel.switch({version})")

    def _on_switch_done(self, ticket) -> None:
        if ticket.status == "completed":
            result = ticket.result or {}
            version = result.get("version", "?")
            self._safe_log(f"{CHECK} Kernel {version} active")
            self._safe_call(self._refresh_list)
            self._safe_call(lambda: self._save_kernel_to_config(result))
        else:
            self._safe_log(f"{CROSS} Switch : {ticket.error}")

    def action_install_kernel(self) -> None:
        """Installe un kernel depuis .deb."""
        source = self.query_one("#source-input", Input).value.strip()
        if not source:
            self.notify("Entrez le chemin du .deb.", severity="warning")
            return
        if not self.bridge:
            return

        self.bridge.emit("kernel.install",
                         source=source,
                         boot_path=self._boot_path,
                         callback=self._on_install_done)
        self._log(f"  -> kernel.install({source})")

    def _on_install_done(self, ticket) -> None:
        if ticket.status == "completed":
            self._safe_log(f"{CHECK} Kernel installe")
            self._safe_call(self._refresh_list)
        else:
            self._safe_log(f"{CROSS} Install : {ticket.error}")

    def action_compile_kernel(self) -> None:
        """Compile un kernel depuis les sources."""
        source_dir = self.query_one("#source-input", Input).value.strip()
        if not source_dir:
            source_dir = "/usr/src/linux"
        if not self.bridge:
            return

        self.bridge.emit("kernel.compile",
                         source_dir=source_dir,
                         callback=self._on_compile_done)
        self._log(f"  -> kernel.compile({source_dir})")
        self.notify("Compilation lancee en arriere-plan (threaded).", timeout=5)

    def _on_compile_done(self, ticket) -> None:
        if ticket.status == "completed":
            result = ticket.result or {}
            version = result.get("version", "?")
            self._safe_log(f"{CHECK} Kernel {version} compile")
            self._safe_call(self._refresh_list)
        else:
            self._safe_log(f"{CROSS} Compilation : {ticket.error}")

    def action_next_step(self) -> None:
        # Sauvegarder le kernel actif
        active = next((k for k in self._kernels if k.get("active")), None)
        if active:
            self._save_kernel_to_config(active)
        if hasattr(self.app, "navigate_next"):
            self.app.navigate_next()

    # ── Config ──────────────────────────────────────────────────────

    def _save_kernel_to_config(self, kernel_info: dict) -> None:
        cfg = getattr(self.app, "config", None)
        if not cfg:
            return
        cfg.set("kernel.active", kernel_info.get("file", ""))
        cfg.set("kernel.version", kernel_info.get("version", ""))
        cfg.set("kernel.modules_path",
                f"/lib/modules/{kernel_info.get('version', '')}")
        try:
            cfg.save()
        except Exception:
            pass

    # ── Snapshot refresh ────────────────────────────────────────────

    def update_from_snapshot(self, snapshot: dict) -> None:
        if not self._kernels:
            return
        for evt in snapshot.get("recent_events", []):
            name = evt.get("name", "")
            if "kernel" in name:
                self._log(f"  [bus] {name}")

    # ── UI helpers ──────────────────────────────────────────────────

    def _log(self, msg: str) -> None:
        try:
            self.query_one("#command-log", Log).write_line(msg)
        except Exception:
            pass

    def _safe_log(self, msg: str) -> None:
        try:
            self.app.call_from_thread(self._log, msg)
        except Exception:
            self._log(msg)

    def _set_status(self, text: str) -> None:
        try:
            self.query_one("#kernel-status", Static).update(
                f"Statut : {text}")
        except Exception:
            pass

    def _safe_call(self, fn) -> None:
        try:
            self.app.call_from_thread(fn)
        except Exception:
            fn()
