# -*- coding: utf-8 -*-
"""
fsdeploy.ui.screens.config_snapshot
======================================
Gestion des snapshots de configuration via bridge.
Compatible : Textual >=8.2.1
"""

import os
import time
from datetime import datetime
from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Label, Log, Static
from textual import on

IS_FB = os.environ.get("TERM") == "linux"
CHECK = "[OK]" if IS_FB else "\u2705"
CROSS = "[!!]" if IS_FB else "\u274c"


class ConfigSnapshotScreen(Screen):

    BINDINGS = [
        Binding("r", "refresh", "Rafraichir", show=True),
        Binding("s", "save", "Sauvegarder", show=True),
        Binding("escape", "app.pop_screen", "Retour", show=False),
    ]

    DEFAULT_CSS = """
    ConfigSnapshotScreen { layout: vertical; }
    #cs-header { height: auto; padding: 1 2; text-style: bold; }
    #cs-status { padding: 0 2; height: 1; color: $text-muted; }
    #snapshot-section { height: 1fr; margin: 0 1; border: solid $primary; padding: 0 1; }
    .table-title { text-style: bold; height: 1; }
    #button-bar { height: 3; padding: 0 2; layout: horizontal; }
    #button-bar Button { margin: 0 1; }
    #command-log { height: 6; margin: 0 1; border: solid $primary-background; padding: 0 1; }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._snapshots: list[dict] = []

    @property
    def bridge(self):
        return getattr(self.app, "bridge", None)

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Snapshots de configuration", id="cs-header")
        yield Static("", id="cs-status")
        with Vertical(id="snapshot-section"):
            yield Label("Snapshots", classes="table-title")
            yield DataTable(id="snapshot-table")
        with Horizontal(id="button-bar"):
            yield Button("Rafraichir", variant="primary", id="btn-refresh")
            yield Button("Sauvegarder", variant="success", id="btn-save")
            yield Button("Restaurer", variant="warning", id="btn-restore")
        yield Log(id="command-log", highlight=True, auto_scroll=True)
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#snapshot-table", DataTable)
        table.add_columns("Nom", "Date", "Taille")
        table.cursor_type = "row"
        self.action_refresh()

    def action_refresh(self) -> None:
        if not self.bridge:
            self._set_status("Bridge indisponible")
            return
        self._log("-> config.snapshot.list")
        self.bridge.emit("config.snapshot.list", callback=self._on_list_done)

    def _on_list_done(self, ticket) -> None:
        if ticket.status == "failed":
            self._safe_log(f"{CROSS} Erreur : {ticket.error}")
            self._set_status("Erreur")
            return
        result = ticket.result or {}
        self._snapshots = result.get("snapshots", [])
        self._refresh_table()
        self._safe_log(f"{CHECK} {len(self._snapshots)} snapshot(s)")
        self._set_status(f"{len(self._snapshots)} snapshot(s)")

    def action_save(self) -> None:
        if not self.bridge:
            return
        name = f"snap_{int(time.time())}"
        self._log(f"-> config.snapshot.save (name={name})")
        self.bridge.emit(
            "config.snapshot.save",
            name=name,
            description="Sauvegarde depuis UI",
            callback=self._on_save_done,
        )

    def _on_save_done(self, ticket) -> None:
        if ticket.status == "failed":
            self._safe_log(f"{CROSS} Sauvegarde echouee : {ticket.error}")
        else:
            name = ticket.params.get("name", "?")
            self._safe_log(f"{CHECK} Snapshot '{name}' sauvegarde")
            self.action_refresh()

    @on(Button.Pressed, "#btn-restore")
    def handle_restore(self) -> None:
        if not self.bridge:
            return
        table = self.query_one("#snapshot-table", DataTable)
        idx = table.cursor_row
        if idx is None or idx >= len(self._snapshots):
            self.notify("Aucun snapshot selectionne", severity="warning")
            return
        snap = self._snapshots[idx]
        name = snap.get("name", "?")
        self._log(f"-> config.snapshot.restore (name={name})")
        self.bridge.emit(
            "config.snapshot.restore",
            name=name,
            callback=self._on_restore_done,
        )

    def _on_restore_done(self, ticket) -> None:
        if ticket.status == "failed":
            self._safe_log(f"{CROSS} Restauration echouee : {ticket.error}")
        else:
            self._safe_log(f"{CHECK} Configuration restauree")
            self.action_refresh()

    @on(Button.Pressed, "#btn-refresh")
    def handle_refresh_btn(self) -> None:
        self.action_refresh()

    @on(Button.Pressed, "#btn-save")
    def handle_save_btn(self) -> None:
        self.action_save()

    def _refresh_table(self) -> None:
        try:
            table = self.query_one("#snapshot-table", DataTable)
            table.clear()
            for snap in self._snapshots:
                mtime = snap.get("mtime", 0)
                dt = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M") if mtime else "?"
                size = snap.get("size", 0)
                size_kb = f"{size / 1024:.1f} KiB" if size else "?"
                table.add_row(snap.get("name", "?"), dt, size_kb)
        except Exception:
            pass

    def _log(self, msg: str) -> None:
        try:
            self.query_one("#command-log", Log).write_line(msg)
        except Exception:
            pass

    def _safe_log(self, msg: str) -> None:
        try:
            self.call_from_thread(self._log, msg)
        except RuntimeError:
            self._log(msg)

    def _set_status(self, text: str) -> None:
        try:
            self.query_one("#cs-status", Static).update(text)
        except Exception:
            pass

    def update_from_snapshot(self, snapshot: Any) -> None:
        pass
