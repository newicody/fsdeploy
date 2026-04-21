"""
Écran de débogage système.
Affiche l'état des overlayfs, des montages, des logs, etc.
"""

import subprocess
from datetime import datetime
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import ScrollableContainer
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, DataTable, TabbedContent, TabPane, Label
from textual.binding import Binding

from fsdeploy.lib.overlay_check import check_all_overlays
from fsdeploy.lib.legacy_mount_check import check_legacy_mounts
from fsdeploy.lib.ui.bridge import SchedulerBridge


class DebugScreen(Screen):
    """
    Écran de débogage.
    """
    
    @property
    def bridge(self):
        return getattr(self, "_bridge", None)

    BINDINGS = [
        Binding("r", "refresh", "Actualiser", show=True),
        Binding("escape", "app.pop_screen", "Retour", show=True),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent(initial="overlay"):
            with TabPane("OverlayFS", id="overlay"):
                yield ScrollableContainer(Static(id="overlay_info", classes="info"))
            with TabPane("Legacy Mounts", id="legacy"):
                yield ScrollableContainer(Static(id="legacy_info", classes="info"))
            with TabPane("Montages", id="mounts"):
                yield ScrollableContainer(Static(id="mount_info", classes="info"))
            with TabPane("Logs", id="logs"):
                yield ScrollableContainer(Static(id="log_info", classes="info"))
        yield Footer()

    def on_mount(self) -> None:
        from fsdeploy.lib.ui.bridge import SchedulerBridge
        self._bridge = SchedulerBridge.default()
        self.action_refresh()

    def action_refresh(self) -> None:
        """Rafraîchit toutes les informations."""
        self.update_overlay()
        self.update_legacy()
        self.update_mounts()
        self.update_logs()

    def update_overlay(self) -> None:
        """Affiche l'état des overlayfs."""
        issues = check_all_overlays()
        widget = self.query_one("#overlay_info", Static)
        if not issues:
            content = "✅ Aucun problème détecté dans les overlayfs."
        else:
            content = "⚠️  Problèmes détectés :\n" + "\n".join(issues)
        widget.update(content)

    def update_legacy(self) -> None:
        """Affiche les problèmes de montages legacy et permissions."""
        issues = check_legacy_mounts()
        widget = self.query_one("#legacy_info", Static)
        if not issues:
            content = "✅ Aucun problème détecté avec les montages legacy."
        else:
            content = "⚠️  Problèmes détectés :\n" + "\n".join(issues)
        widget.update(content)

    def update_mounts(self) -> None:
        """Affiche les montages importants."""
        try:
            proc = subprocess.run(
                ["mount"], capture_output=True, text=True, timeout=5
            )
            mounts = proc.stdout.splitlines()
            # Filtrer les montages intéressants
            interesting = [
                m for m in mounts
                if any(x in m.lower() for x in ["zfs", "overlay", "squashfs", "boot", "efi"])
            ]
            content = "\n".join(interesting[:30])  # limite
        except Exception as e:
            content = f"Erreur : {e}"
        widget = self.query_one("#mount_info", Static)
        widget.update(content)

    def update_logs(self) -> None:
        """Affiche la taille des logs."""
        log_dir = Path("/var/log")
        fsdeploy_log = log_dir / "fsdeploy"
        lines = []
        if fsdeploy_log.exists():
            for f in fsdeploy_log.glob("*.log"):
                size = f.stat().st_size
                lines.append(f"{f.name}: {size} octets")
        if not lines:
            lines.append("Aucun log fsdeploy trouvé.")
        widget = self.query_one("#log_info", Static)
        widget.update("\n".join(lines))
