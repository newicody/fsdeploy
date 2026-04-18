# add.md — 19.2a : Câbler SecurityScreen au bridge

## Fichier : `fsdeploy/lib/ui/screens/security.py`

L'écran affiche actuellement des données fictives codées en dur. L'intent `security.status` et la task `SecurityStatusTask` existent déjà et retournent les vraies règles. Il faut câbler l'écran pour utiliser `bridge.emit()`.

## Réécrire le fichier complet :

```python
# -*- coding: utf-8 -*-
"""
fsdeploy.ui.screens.security
===============================
Ecran Security : regles de securite et decorateurs.
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
CROSS = "[!!]" if IS_FB else "\u274c"


class SecurityScreen(Screen):

    BINDINGS = [
        Binding("r", "refresh", "Rafraichir", show=True),
        Binding("escape", "app.pop_screen", "Retour", show=False),
    ]

    DEFAULT_CSS = """
    SecurityScreen { layout: vertical; }
    #security-header { height: auto; padding: 1 2; text-style: bold; }
    #security-status { padding: 0 2; height: 1; color: $text-muted; }
    #rules-section { height: 1fr; margin: 0 1; border: solid $primary; padding: 0 1; }
    .table-title { text-style: bold; height: 1; }
    #command-log { height: 6; margin: 0 1; border: solid $primary-background; padding: 0 1; }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._rules: list[tuple[str, str, str]] = []

    @property
    def bridge(self):
        return getattr(self.app, "bridge", None)

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Securite", id="security-header")
        yield Static("Statut : en attente", id="security-status")
        with Vertical(id="rules-section"):
            yield Label("Regles de securite", classes="table-title")
            yield DataTable(id="rules-table")
        yield Log(id="command-log", highlight=True, auto_scroll=True)
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#rules-table", DataTable)
        table.add_columns("Type", "Chemin", "Valeur")
        table.cursor_type = "row"
        self.action_refresh()

    def action_refresh(self) -> None:
        if not self.bridge:
            self._set_status("Bridge indisponible")
            return
        self._set_status("Chargement...")
        self._log("-> security.status")
        self.bridge.emit("security.status", callback=self._on_security_done)

    def _on_security_done(self, ticket) -> None:
        if ticket.status == "failed":
            self._safe_log(f"{CROSS} Erreur : {ticket.error}")
            self._set_status("Erreur")
            return
        result = ticket.result or {}
        rules = result.get("rules", {})
        decorators = result.get("registered_decorators", [])
        config_path = result.get("config_path", "?")

        self._rules = []
        for key, val in rules.items():
            self._rules.append(("regle", key, str(val)))
        for dec in decorators:
            self._rules.append(("decorateur", dec, "actif"))

        self._refresh_table()
        self._safe_log(f"{CHECK} {len(rules)} regles, {len(decorators)} decorateurs")
        self._set_status(f"Config : {config_path} - {len(self._rules)} entrees")

    def _refresh_table(self) -> None:
        try:
            table = self.query_one("#rules-table", DataTable)
            table.clear()
            for row in self._rules:
                table.add_row(*row)
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
            self.query_one("#security-status", Static).update(text)
        except Exception:
            pass

    def update_from_snapshot(self, snapshot: Any) -> None:
        pass
```

## Critères

1. `grep "bridge.emit" fsdeploy/lib/ui/screens/security.py` → contient `security.status`
2. Aucune donnée fictive codée en dur
3. Le pattern callback (`_on_security_done`) suit le même modèle que `detection.py`
4. Aucun import depuis `lib/` (hors ui/)
