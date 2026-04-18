# -*- coding: utf-8 -*-
"""
fsdeploy.ui.screens.crosscompile
===================================
Cross-compilation kernel pour autres architectures.
Compatible : Textual >=8.2.1
"""

import os
from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Label, Log, Static
from textual import on

IS_FB = os.environ.get("TERM") == "linux"
CHECK = "[OK]" if IS_FB else "\u2705"
CROSS_ICON = "[!!]" if IS_FB else "\u274c"

ARCHITECTURES = [
    ("aarch64", "gcc-aarch64-linux-gnu"),
    ("riscv64", "gcc-riscv64-linux-gnu"),
    ("armhf", "gcc-arm-linux-gnueabihf"),
    ("mips64el", "gcc-mips64el-linux-gnuabi64"),
]


class CrossCompileScreen(Screen):

    BINDINGS = [
        Binding("r", "refresh", "Rafraichir", show=True),
        Binding("escape", "app.pop_screen", "Retour", show=False),
    ]

    DEFAULT_CSS = """
    CrossCompileScreen { layout: vertical; }
    #cc-header { height: auto; padding: 1 2; text-style: bold; }
    #cc-status { padding: 0 2; height: 1; color: $text-muted; }
    #arch-section { height: 1fr; margin: 0 1; border: solid $primary; padding: 0 1; }
    .table-title { text-style: bold; height: 1; }
    #button-bar { height: 3; padding: 0 2; layout: horizontal; }
    #button-bar Button { margin: 0 1; }
    #command-log { height: 6; margin: 0 1; border: solid $primary-background; padding: 0 1; }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @property
    def bridge(self):
        return getattr(self.app, "bridge", None)

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Cross-compilation kernel", id="cc-header")
        yield Static("", id="cc-status")
        with Vertical(id="arch-section"):
            yield Label("Architectures", classes="table-title")
            yield DataTable(id="arch-table")
        with Horizontal(id="button-bar"):
            yield Button("Compiler", variant="success", id="btn-compile")
            yield Button("Rafraichir", variant="primary", id="btn-refresh")
        yield Log(id="command-log", highlight=True, auto_scroll=True)
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#arch-table", DataTable)
        table.add_columns("Architecture", "Toolchain", "Statut")
        table.cursor_type = "row"
        self.action_refresh()

    def action_refresh(self) -> None:
        if not self.bridge:
            self._set_status("Bridge indisponible")
            return
        self._log("-> kernel.registry.scan")
        self.bridge.emit("kernel.registry.scan", callback=self._on_scan_done)

    def _on_scan_done(self, ticket) -> None:
        table = self.query_one("#arch-table", DataTable)
        table.clear()
        if ticket.status == "failed":
            self._safe_log(f"{CROSS_ICON} Erreur : {ticket.error}")
            for arch, tc in ARCHITECTURES:
                table.add_row(arch, tc, "inconnu")
        else:
            result = ticket.result or {}
            kernels = result.get("kernels", {})
            for arch, tc in ARCHITECTURES:
                found = any(k.get("arch") == arch for k in kernels.values()) if isinstance(kernels, dict) else False
                status = f"{CHECK} disponible" if found else "absent"
                table.add_row(arch, tc, status)
            self._safe_log(f"{CHECK} Scan termine")
        self._set_status(f"{len(ARCHITECTURES)} architectures")

    @on(Button.Pressed, "#btn-compile")
    def handle_compile(self) -> None:
        if not self.bridge:
            return
        table = self.query_one("#arch-table", DataTable)
        idx = table.cursor_row
        if idx is None or idx >= len(ARCHITECTURES):
            self.notify("Selectionnez une architecture", severity="warning")
            return
        arch, toolchain = ARCHITECTURES[idx]
        self._log(f"-> kernel.compile (arch={arch})")
        self.bridge.emit("kernel.compile", architecture=arch, toolchain=toolchain, callback=self._on_compile_done)

    def _on_compile_done(self, ticket) -> None:
        if ticket.status == "failed":
            self._safe_log(f"{CROSS_ICON} Compilation echouee : {ticket.error}")
        else:
            self._safe_log(f"{CHECK} Compilation terminee")

    @on(Button.Pressed, "#btn-refresh")
    def handle_refresh_btn(self) -> None:
        self.action_refresh()

    def _log(self, msg):
        try: self.query_one("#command-log", Log).write_line(msg)
        except Exception: pass

    def _safe_log(self, msg):
        try: self.call_from_thread(self._log, msg)
        except RuntimeError: self._log(msg)

    def _set_status(self, text):
        try: self.query_one("#cc-status", Static).update(text)
        except Exception: pass

    def update_from_snapshot(self, s: Any) -> None:
        pass
