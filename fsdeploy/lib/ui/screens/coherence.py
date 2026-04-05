"""
fsdeploy.ui.screens.coherence — Verification coherence avant boot, 100% bus events.
"""

import os
from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Label, Log, Static

IS_FB = os.environ.get("TERM") == "linux"
CHECK, CROSS, WARN, ARROW = ("[OK]","[!!]","[??]","->") if IS_FB else ("✅","❌","⚠️","→")

class CoherenceScreen(Screen):

    BINDINGS = [
        Binding("r", "run_check", "Verifier", show=True),
        Binding("enter", "next_step", "Suivant", show=True),
        Binding("escape", "app.pop_screen", "Retour", show=False),
    ]

    DEFAULT_CSS = """
    CoherenceScreen { layout: vertical; }
    #coherence-header { height: auto; padding: 1 2; text-style: bold; }
    #coherence-status { padding: 0 2; height: 1; color: $text-muted; }
    #coherence-summary { height: auto; padding: 1 2; margin: 0 1;
                         border: solid $primary; }
    #checks-table-section { height: 1fr; margin: 0 1;
                            border: solid $primary; padding: 0 1; }
    #command-log { height: 6; margin: 0 1; border: solid $primary-background;
                   padding: 0 1; }
    #action-buttons { height: 3; padding: 0 2; layout: horizontal; }
    #action-buttons Button { margin: 0 1; }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
self._checks: list[dict] = []
        self._passed: bool = False

    @property
    def bridge(self):
        return getattr(self.app, "bridge", None)

    def compose(self) -> ComposeResult:
        yield Static("Verification de coherence", id="coherence-header")
        yield Static("Statut : en attente", id="coherence-status")

        with Vertical(id="coherence-summary"):
            yield Label("Resultat", classes="info-label")
            yield Label("Lancez une verification.", id="summary-label")

        with Vertical(id="checks-table-section"):
            yield Label("Verifications")
            yield DataTable(id="checks-table")

        yield Log(id="command-log", highlight=True, auto_scroll=True)

        with Horizontal(id="action-buttons"):
            yield Button("Verifier", variant="primary", id="btn-check")
            yield Button(f"Suivant {ARROW}", variant="success", id="btn-next",
                         disabled=True)

    def on_mount(self) -> None:
        dt = self.query_one("#checks-table", DataTable)
        dt.add_columns("", "Verification", "Resultat", "Severite")
        dt.cursor_type = "row"
        self.action_run_check()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "btn-check": self.action_run_check()
        elif bid == "btn-next": self.action_next_step()

    def action_run_check(self) -> None:
        if not self.bridge: return
        cfg = getattr(self.app, "config", None)
        boot_path = cfg.get("pool.boot_mount", "/boot") if cfg else "/boot"
        active_preset = cfg.get("presets.active", "") if cfg else ""
        preset_data = {}
        if active_preset and cfg:
            preset_data = dict(cfg.get(f"presets.{active_preset}", {}))

        self._set_status("Verification en cours...")
        self.bridge.emit("coherence.check",
                         boot_path=boot_path, preset=preset_data,
                         callback=self._on_check_done)
        self._log("-> coherence.check")

    def _on_check_done(self, ticket) -> None:
        if ticket.status == "completed":
            result = ticket.result
            if hasattr(result, "checks"):
                self._checks = [{"name": c.name, "passed": c.passed,
                                  "message": c.message, "severity": c.severity}
                                for c in result.checks]
                self._passed = result.passed
                summary = result.summary()
            elif isinstance(result, dict):
                self._checks = result.get("checks", [])
                self._passed = result.get("passed", False)
                summary = result.get("summary", "")
            else:
                self._checks = []
                self._passed = False
                summary = str(result)

            self._safe_call(self._refresh_display)
            self._safe_call(lambda: self._set_summary(summary))
        else:
            self._safe_call(lambda: self._set_status(f"{CROSS} {ticket.error}"))

    def _refresh_display(self) -> None:
        dt = self.query_one("#checks-table", DataTable)
        dt.clear()
        for c in self._checks:
            icon = CHECK if c.get("passed") else (
                CROSS if c.get("severity") == "error" else WARN)
            dt.add_row(icon, c.get("name","?"),
                       c.get("message","")[:60], c.get("severity","?"))

        icon = CHECK if self._passed else CROSS
        self._set_status(f"{icon} {'Systeme coherent' if self._passed else 'Erreurs detectees'}")
        self.query_one("#btn-next", Button).disabled = not self._passed

    def _set_summary(self, text: str) -> None:
        try: self.query_one("#summary-label", Label).update(text)
        except Exception: pass

    def action_next_step(self) -> None:
        if not self._passed:
            self.notify("Corrigez les erreurs d'abord.", severity="warning")
            return
        if hasattr(self.app, "navigate_next"): self.app.navigate_next()

    def update_from_snapshot(self, s: dict) -> None: pass
    def _log(self, m):
        try: self.query_one("#command-log", Log).write_line(m)
        except Exception: pass
    def _safe_call(self, fn):
        try: self.app.call_from_thread(fn)
        except Exception: fn()
    def _set_status(self, t):
        try: self.query_one("#coherence-status", Static).update(f"Statut : {t}")
        except Exception: pass
