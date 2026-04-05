"""
fsdeploy.ui.screens.welcome
=============================
Écran d'accueil.

Deux modes :
  - deploy : présente le système détecté, propose de lancer le workflow
  - booted : grille d'actions rapides pour la gestion courante

Affiche :
  - Infos hardware (CPU, RAM, arch)
  - Mode détecté (live / booted / initramfs)
  - Pools ZFS détectés
  - Version fsdeploy
  - Stats du HuffmanStore (si disponible)
"""

import os
import platform
from pathlib import Path
from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, Container
from textual.screen import Screen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Label,
    Static,
    Rule,
)

# ── Détection framebuffer ─────────────────────────────────────────────────────

IS_FB = os.environ.get("TERM") == "linux"

# Caractères sûrs pour framebuffer
BULLET = "-" if IS_FB else "•"
CHECK  = "[OK]" if IS_FB else "✅"
CROSS  = "[!!]" if IS_FB else "❌"
WARN   = "[??]" if IS_FB else "⚠️"
ARROW  = "->" if IS_FB else "→"
BOX_H  = "=" if IS_FB else "═"

# ═════════════════════════════════════════════════════════════════════════════
# WIDGETS INTERNES
# ═════════════════════════════════════════════════════════════════════════════

class InfoRow(Horizontal):
    """Ligne clé: valeur dans le panneau d'info."""

    DEFAULT_CSS = """
    InfoRow {
        height: 1;
        padding: 0 1;
    }
    InfoRow .info-key {
        width: 20;
        text-style: bold;
        color: $text-muted;
    }
    InfoRow .info-val {
        width: 1fr;
    }
    """

    def __init__(self, key: str, value: str, **kwargs):
        super().__init__(**kwargs)
        self._key = key
        self._value = value

    def compose(self) -> ComposeResult:
        yield Label(self._key, classes="info-key")
        yield Label(self._value, classes="info-val")

class ActionCard(Button):
    """Bouton d'action dans la grille du mode booted."""

    DEFAULT_CSS = """
    ActionCard {
        width: 1fr;
        height: 5;
        margin: 1;
        content-align: center middle;
    }
    """

    def __init__(self, label: str, screen_name: str, shortcut: str = "", **kwargs):
        display_label = f"{label}\n[{shortcut}]" if shortcut else label
        super().__init__(display_label, **kwargs)
        self.screen_name = screen_name

# ═════════════════════════════════════════════════════════════════════════════
# WELCOME SCREEN
# ═════════════════════════════════════════════════════════════════════════════

class WelcomeScreen(Screen):
    """Écran d'accueil fsdeploy."""

    BINDINGS = [
        Binding("enter", "start_workflow", "Commencer", show=True),
        Binding("r", "refresh_info", "Rafraîchir", show=True),
        Binding("escape", "app.pop_screen", "Retour", show=False),
    ]

    DEFAULT_CSS = """
    WelcomeScreen {
        layout: vertical;
        overflow-y: auto;
    }

    #welcome-banner {
        width: 100%;
        height: auto;
        content-align: center middle;
        text-align: center;
        padding: 1 0;
        color: $accent;
        text-style: bold;
    }

    #welcome-subtitle {
        width: 100%;
        height: auto;
        text-align: center;
        color: $text-muted;
        padding: 0 0 1 0;
    }

    #info-container {
        height: auto;
        margin: 0 2;
    }

    #system-panel {
        height: auto;
        border: solid $primary;
        padding: 1 2;
        margin: 1;
    }

    #pools-panel {
        height: auto;
        border: solid $primary;
        padding: 1 2;
        margin: 1;
    }

    #store-panel {
        height: auto;
        border: solid $accent;
        padding: 1 2;
        margin: 1;
    }

    #actions-grid {
        layout: grid;
        grid-size: 3 4;
        grid-gutter: 1;
        padding: 1 2;
        height: auto;
    }

    #deploy-actions {
        height: auto;
        padding: 1 2;
        content-align: center middle;
    }

    #deploy-actions Button {
        margin: 1 2;
    }

    .panel-title {
        text-style: bold;
        margin-bottom: 1;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
self._env_info: dict[str, Any] = {}
        self._pools: list[dict] = []
        self._snapshot: dict[str, Any] = {}

    # ── Compose ───────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Static(self._banner_text(), id="welcome-banner")
        yield Static(self._subtitle_text(), id="welcome-subtitle")
        yield Rule()

        with Container(id="info-container"):
            # Panneau système
            with Vertical(id="system-panel"):
                yield Label("Systeme", classes="panel-title")
                yield InfoRow("Mode", "...")
                yield InfoRow("Init system", "...")
                yield InfoRow("Architecture", "...")
                yield InfoRow("CPU", "...")
                yield InfoRow("RAM", "...")
                yield InfoRow("Reseau", "...")
                yield InfoRow("Affichage", "...")
                yield InfoRow("Config", "...")

            # Panneau pools
            with Vertical(id="pools-panel"):
                yield Label("Pools ZFS", classes="panel-title")
                yield DataTable(id="pools-table")

            # Panneau store (si disponible)
            with Vertical(id="store-panel"):
                yield Label("Runtime", classes="panel-title")
                yield InfoRow("Events", "0")
                yield InfoRow("Tasks", "0")
                yield InfoRow("Locks", "0")
                yield InfoRow("Compression", "N/A")

        yield Rule()

        # Actions selon le mode
        if self._is_deploy_mode():
            with Horizontal(id="deploy-actions"):
                yield Button(
                    f"Commencer le deploiement {ARROW}",
                    variant="primary",
                    id="btn-start",
                )
                yield Button(
                    "Mode debug",
                    variant="default",
                    id="btn-debug",
                )
        else:
            with Container(id="actions-grid"):
                yield ActionCard("Detection", "detection", "d")
                yield ActionCard("Montages", "mounts", "m")
                yield ActionCard("Kernel", "kernel", "k")
                yield ActionCard("Initramfs", "initramfs", "i")
                yield ActionCard("Presets", "presets", "p")
                yield ActionCard("Coherence", "coherence", "c")
                yield ActionCard("Snapshots", "snapshots", "s")
                yield ActionCard("Stream", "stream", "y")
                yield ActionCard("Config", "config", "o")
                yield ActionCard("Debug", "debug", "x")
                yield ActionCard("ZFSBootMenu", "zbm", "z")
                yield ActionCard("Statut pools", "status", "t")

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def on_mount(self) -> None:
        """Initialisation après montage."""
        self._detect_system()
        self._detect_pools()
        self._update_display()

    # ── Détection système ─────────────────────────────────────────────────────

    def _detect_system(self) -> None:
        """Détecte l'environnement système."""
        self._env_info = {
            "mode": self._detect_mode(),
            "init_system": self._detect_init_system(),
            "arch": platform.machine(),
            "cpu": self._get_cpu_model(),
            "ram_mb": self._get_ram_mb(),
            "network": self._check_network(),
            "display": "framebuffer" if IS_FB else os.environ.get("TERM", "unknown"),
            "config_path": self._find_config_path(),
        }

    def _detect_mode(self) -> str:
        """Détecte le mode d'exécution."""
        # Vérifier si le daemon nous a passé le mode
        app = self.app
        if hasattr(app, "deploy_mode"):
            return app.deploy_mode

        # Heuristiques
        cmdline = self._read_file("/proc/cmdline")
        if any(k in cmdline.lower() for k in ("boot=live", "live-media")):
            return "live (deploy)"
        if Path("/run/live").is_dir():
            return "live (deploy)"
        if os.getpid() == 1:
            return "initramfs"
        return "booted"

    def _detect_init_system(self) -> str:
        if Path("/run/systemd/system").is_dir():
            return "systemd"
        if Path("/sbin/openrc").exists():
            return "openrc"
        if Path("/etc/init.d").is_dir():
            return "sysvinit"
        return "unknown"

    def _get_cpu_model(self) -> str:
        cpuinfo = self._read_file("/proc/cpuinfo")
        for line in cpuinfo.splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
        return platform.processor() or "unknown"

    def _get_ram_mb(self) -> int:
        meminfo = self._read_file("/proc/meminfo")
        for line in meminfo.splitlines():
            if line.startswith("MemTotal"):
                return int(line.split()[1]) // 1024
        return 0

    def _check_network(self) -> str:
        try:
            for iface in Path("/sys/class/net").iterdir():
                if iface.name == "lo":
                    continue
                state = self._read_file(str(iface / "operstate")).strip()
                if state == "up":
                    return f"oui ({iface.name})"
        except OSError:
            pass
        return "non"

    def _find_config_path(self) -> str:
        app = self.app
        if hasattr(app, "config") and app.config:
            return str(getattr(app.config, "path", "N/A"))
        for p in ["/boot/fsdeploy/fsdeploy.conf",
                   "/etc/fsdeploy/fsdeploy.conf"]:
            if Path(p).exists():
                return p
        return "non trouve"

    def _detect_pools(self) -> None:
        """Détecte les pools ZFS importés."""
        self._pools = []
        try:
            import subprocess
            result = subprocess.run(
                ["zpool", "list", "-H", "-o", "name,size,alloc,free,health"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                for line in result.stdout.strip().splitlines():
                    parts = line.split("\t")
                    if len(parts) >= 5:
                        self._pools.append({
                            "name": parts[0],
                            "size": parts[1],
                            "alloc": parts[2],
                            "free": parts[3],
                            "health": parts[4],
                        })
        except Exception:
            pass

    # ── Mise à jour de l'affichage ────────────────────────────────────────────

    def _update_display(self) -> None:
        """Met à jour tous les widgets avec les données détectées."""
        # Système
        info_rows = self.query("InfoRow").results()
        row_list = list(info_rows)

        # Dans le panneau système (les 8 premières InfoRow)
        system_values = [
            self._env_info.get("mode", "?"),
            self._env_info.get("init_system", "?"),
            self._env_info.get("arch", "?"),
            self._env_info.get("cpu", "?"),
            f"{self._env_info.get('ram_mb', 0)} MB",
            self._env_info.get("network", "?"),
            self._env_info.get("display", "?"),
            self._env_info.get("config_path", "?"),
        ]

        for i, val in enumerate(system_values):
            if i < len(row_list):
                # Mettre à jour la valeur (deuxième Label enfant)
                labels = list(row_list[i].query("Label").results())
                if len(labels) >= 2:
                    labels[1].update(val)

        # Pools
        try:
            table = self.query_one("#pools-table", DataTable)
            table.clear(columns=True)
            table.add_columns("Pool", "Taille", "Utilise", "Libre", "Sante")
            if self._pools:
                for p in self._pools:
                    health = p["health"]
                    table.add_row(
                        p["name"],
                        p["size"],
                        p["alloc"],
                        p["free"],
                        health,
                    )
            else:
                table.add_row("(aucun pool detecte)", "-", "-", "-", "-")
        except Exception:
            pass

    def update_from_snapshot(self, snapshot: dict) -> None:
        """
        Appelé par FsDeployApp._refresh_from_store().

        Met à jour le panneau Runtime avec les stats du HuffmanStore.
        """
        self._snapshot = snapshot
        counts = snapshot.get("counts", {})
        codec = snapshot.get("codec", {})

        # Mettre à jour les InfoRow du store-panel
        # Les InfoRow du store-panel sont les 4 dernières
        info_rows = list(self.query("InfoRow").results())
        store_rows = info_rows[-4:] if len(info_rows) >= 12 else []

        store_values = [
            str(counts.get("events", 0)),
            str(counts.get("tasks", 0)),
            str(counts.get("locks", 0)),
            f"{codec.get('ratio', 1.0):.1%}" if codec.get("ratio") else "N/A",
        ]

        for i, val in enumerate(store_values):
            if i < len(store_rows):
                labels = list(store_rows[i].query("Label").results())
                if len(labels) >= 2:
                    labels[1].update(val)

    # ── Événements ────────────────────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Gestion des clics sur les boutons."""
        button_id = event.button.id or ""

        if button_id == "btn-start":
            self.action_start_workflow()
        elif button_id == "btn-debug":
            self.app.action_switch_screen("debug")
        elif isinstance(event.button, ActionCard):
            self.app.action_switch_screen(event.button.screen_name)

    def action_start_workflow(self) -> None:
        """Lance le workflow de déploiement."""
        if hasattr(self.app, "navigate_next"):
            self.app.navigate_next()
        else:
            self.app.action_switch_screen("detection")

    def action_refresh_info(self) -> None:
        """Rafraîchit les informations système."""
        self._detect_system()
        self._detect_pools()
        self._update_display()
        self.notify("Informations rafraichies.", timeout=2)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _is_deploy_mode(self) -> bool:
        app = self.app
        if hasattr(app, "deploy_mode"):
            return app.deploy_mode in ("deploy", "live")
        return "live" in self._env_info.get("mode", "").lower()

    def _banner_text(self) -> str:
        if IS_FB:
            return (
                "========================================\n"
                "     fsdeploy - ZFS Boot Manager\n"
                "========================================"
            )
        return (
            "╔══════════════════════════════════════╗\n"
            "║     fsdeploy — ZFS Boot Manager      ║\n"
            "╚══════════════════════════════════════╝"
        )

    def _subtitle_text(self) -> str:
        import fsdeploy
        return f"v{fsdeploy.__version__} — Deploiement et gestion ZFS/ZFSBootMenu"

    @staticmethod
    def _read_file(path: str) -> str:
        try:
            return Path(path).read_text(errors="replace")
        except OSError:
            return ""
