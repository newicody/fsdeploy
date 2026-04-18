# -*- coding: utf-8 -*-
"""
fsdeploy.ui.screens.multiarch
================================
Support multi-architecture.
Compatible : Textual >=8.2.1
"""

import os
from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Label, Log, Static

IS_FB = os.environ.get("TERM") == "linux"
CHECK = "[OK]" if IS_FB else "\u2705"
CROSS_ICON = "[!!]" if IS_FB else "\u274c"


class MultiArchScreen(Screen):

    BINDINGS = [
        Binding("r", "refresh", "Rafraichir", show=True),
        Binding("escape", "app.pop_screen", "Retour", show=False),
    ]

    DEFAULT_CSS = """
    MultiArchScreen { layout: vertical; }
    #ma-header { height: auto; padding: 1 2; text-style: bold; }
    #ma-status { padding: 0 2; height: 1; color: $text-muted; }
    #kernel-section { height: 1fr; margin: 0 1; border: solid $primary; padding: 0 1; }
    .table-title { text-style: bold; height: 1; }
    #command-log { height: 6; margin: 0 1; border: solid $primary-background; padding: 0 1; }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @property
    def bridge(self):
        return getattr(self.app, "bridge", None)

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Multi-architecture", id="ma-header")
        yield Static("", id="ma-status")
        with Vertical(id="kernel-section"):
            yield Label("Kernels par architecture", classes="table-title")
            yield DataTable(id="kernel-table")
        yield Log(id="command-log", highlight=True, auto_scroll=True)
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#kernel-table", DataTable)
        table.add_columns("Architecture", "Kernel", "Initramfs", "Boot")
        table.cursor_type = "row"
        self.action_refresh()

    def action_refresh(self) -> None:
        if not self.bridge:
            self._set_status("Bridge indisponible")
            return
        self._log("-> kernel.list")
        self.bridge.emit("kernel.list", callback=self._on_list_done)

    def _on_list_done(self, ticket) -> None:
        table = self.query_one("#kernel-table", DataTable)
        table.clear()
        if ticket.status == "failed":
            self._safe_log(f"{CROSS_ICON} Erreur : {ticket.error}")
            self._set_status("Erreur")
            return
        result = ticket.result or {}
        kernels = result.get("kernels", [])
        if isinstance(kernels, dict):
            kernels = list(kernels.values())
        for k in kernels:
            arch = k.get("arch", "amd64")
            version = k.get("version", k.get("name", "?"))
            initramfs = k.get("initramfs", "?")
            boot = k.get("boot_type", "?")
            table.add_row(arch, version, initramfs, boot)
        self._safe_log(f"{CHECK} {len(kernels)} kernel(s)")
        self._set_status(f"{len(kernels)} kernel(s) trouves")

    def _log(self, msg):
        try: self.query_one("#command-log", Log).write_line(msg)
        except Exception: pass

    def _safe_log(self, msg):
        try: self.call_from_thread(self._log, msg)
        except RuntimeError: self._log(msg)

    def _set_status(self, text):
        try: self.query_one("#ma-status", Static).update(text)
        except Exception: pass

    def update_from_snapshot(self, s: Any) -> None:
        pass
