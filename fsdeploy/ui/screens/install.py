"""
fsdeploy.ui.screens.install
============================
Écran Textual pour SystemInstaller.

Utilisé dans LES DEUX modes :

  Mode live (installateur Debian)
    → mountpoint = Path("/mnt/target") choisi sur MountsScreen
    → installe cron + service + logrotate dans le rootfs cible

  Mode booted (système installé, UI post-boot)
    → mountpoint = Path("/")
    → installe/met à jour sur le système courant
    → permet de switcher le service (désactiver/réactiver) à chaud

L'écran utilise le même CommandLog que tous les autres écrans —
toutes les commandes et leurs sorties apparaissent en temps réel.

Widgets :
    ┌─────────────────────────────────────────────────┐
    │  InstallScreen                                  │
    │                                                 │
    │  [StatusPanel]   init détecté, état composants  │
    │  [CommandLog]    log des opérations en live      │
    │  [Buttons]       Install All / Uninstall / Back  │
    └─────────────────────────────────────────────────┘

Intégration dans FsDeployApp :
    from fsdeploy.ui.screens.install import InstallScreen
    self.push_screen(InstallScreen(mountpoint=Path("/mnt/target")))
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.screen import Screen
from textual.widgets import (
    Button,
    Label,
    LoadingIndicator,
    Static,
)

from fsdeploy.config import FsDeployConfig
from fsdeploy.core.install import (
    InstallResult,
    InstallStatus,
    SystemInstaller,
    detect_init_system,
)
from fsdeploy.core.runner import CommandRunner
from fsdeploy.ui.widgets.command_log import CommandLog
from fsdeploy.ui.widgets.confirm_dialog import ConfirmDialog


# =============================================================================
# WIDGET STATUT
# =============================================================================

class InstallStatusPanel(Static):
    """
    Panneau d'état des composants installés.
    Mis à jour après chaque opération via refresh_status().
    """

    DEFAULT_CSS = """
    InstallStatusPanel {
        border: solid $accent;
        padding: 1 2;
        height: auto;
        margin-bottom: 1;
    }
    InstallStatusPanel .section-title {
        text-style: bold;
        color: $accent;
    }
    InstallStatusPanel .ok    { color: $success; }
    InstallStatusPanel .fail  { color: $error; }
    InstallStatusPanel .warn  { color: $warning; }
    """

    def __init__(self, mountpoint: Path) -> None:
        super().__init__()
        self.mountpoint = mountpoint

    def compose(self) -> ComposeResult:
        yield Label("Détection du système…", classes="section-title")

    def refresh_status(self, status: dict) -> None:
        """Recharge le panneau avec les données de SystemInstaller.status()."""
        init_label   = status["init_label"]
        is_live      = status["is_live"]
        components   = status["components"]

        def icon(c: dict) -> str:
            return "✅" if c["installed"] else "❌"

        live_str = f" [Live → {self.mountpoint}]" if is_live else ""
        text = (
            f"[bold]Init détecté[/] : {init_label}{live_str}\n"
            f"\n"
            f"[bold]Composants[/]\n"
            f"  {icon(components['cron'])}      cron         {components['cron'].get('path','')}\n"
            f"  {icon(components['logrotate'])} logrotate    {components['logrotate'].get('path','')}\n"
            f"  {icon(components['service'])}   service      {components['service'].get('path','')}\n"
        )
        self.update(text)


# =============================================================================
# ÉCRAN PRINCIPAL
# =============================================================================

class InstallScreen(Screen):
    """
    Écran d'installation des composants système fsdeploy.

    Args:
        mountpoint: Racine du rootfs cible.
                    Path("/") pour le système courant.
                    Path("/mnt/xxx") pour un rootfs live.
        cfg:        FsDeployConfig (utilise FsDeployConfig.default() si None).
        dry_run:    Si True, aucune modification sur le disque.
    """

    BINDINGS = [
        ("escape", "go_back", "Retour"),
        ("i",      "install",   "Installer"),
        ("u",      "uninstall", "Désinstaller"),
        ("r",      "refresh",   "Rafraîchir"),
    ]

    DEFAULT_CSS = """
    InstallScreen {
        layout: vertical;
    }
    #header {
        dock: top;
        height: 3;
        background: $boost;
        padding: 0 2;
        content-align: left middle;
        text-style: bold;
        color: $accent;
    }
    #main-container {
        layout: vertical;
        height: 1fr;
    }
    #log-container {
        height: 1fr;
        border: solid $surface;
    }
    #buttons {
        dock: bottom;
        height: 3;
        layout: horizontal;
        padding: 0 2;
        background: $boost;
    }
    #buttons Button {
        margin-right: 2;
    }
    #loading {
        display: none;
        height: 3;
    }
    """

    def __init__(
        self,
        mountpoint: Path | str = Path("/"),
        cfg: FsDeployConfig | None = None,
        dry_run: bool = False,
    ) -> None:
        super().__init__()
        self.mountpoint = Path(mountpoint)
        self.cfg        = cfg or FsDeployConfig.default()
        self.dry_run    = dry_run
        self._installer: SystemInstaller | None = None
        self._runner:    CommandRunner | None    = None

    # ── Composition ──────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        is_live = self.mountpoint != Path("/")
        title   = (
            f"Installation système — rootfs : {self.mountpoint}"
            if is_live
            else "Installation système — système courant"
        )

        yield Label(title, id="header")

        with Vertical(id="main-container"):
            yield InstallStatusPanel(self.mountpoint)
            yield LoadingIndicator(id="loading")

            with ScrollableContainer(id="log-container"):
                yield CommandLog(id="cmd-log")

        with Horizontal(id="buttons"):
            yield Button("Installer tout",   id="btn-install",   variant="primary")
            yield Button("Désinstaller",     id="btn-uninstall", variant="error")
            yield Button("Rafraîchir état",  id="btn-refresh",   variant="default")
            yield Button("Retour",           id="btn-back",      variant="default")

    def on_mount(self) -> None:
        """Initialise le runner et rafraîchit le statut au montage."""
        cmd_log      = self.query_one("#cmd-log", CommandLog)
        self._runner = CommandRunner(dry_run=self.dry_run, log_sink=cmd_log.append)
        self._installer = SystemInstaller(
            cfg=self.cfg,
            runner=self._runner,
            mountpoint=self.mountpoint,
            on_progress=self._on_progress,
        )
        self._do_refresh()

    # ── Callbacks de progression ──────────────────────────────────────────────

    def _on_progress(self, step: str, detail: str) -> None:
        """Appelé par SystemInstaller à chaque étape — met à jour l'UI."""
        cmd_log = self.query_one("#cmd-log", CommandLog)
        cmd_log.append(f"[cyan]▶ {step}[/]  {detail}")

    # ── Actions ───────────────────────────────────────────────────────────────

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def action_refresh(self) -> None:
        self._do_refresh()

    def action_install(self) -> None:
        self._do_install()

    def action_uninstall(self) -> None:
        self._do_uninstall()

    # ── Boutons ───────────────────────────────────────────────────────────────

    @on(Button.Pressed, "#btn-back")
    def _back(self) -> None:
        self.action_go_back()

    @on(Button.Pressed, "#btn-refresh")
    def _refresh(self) -> None:
        self._do_refresh()

    @on(Button.Pressed, "#btn-install")
    def _install(self) -> None:
        self._do_install()

    @on(Button.Pressed, "#btn-uninstall")
    def _uninstall(self) -> None:
        self._do_uninstall()

    # ── Workers (async) ───────────────────────────────────────────────────────

    def _do_refresh(self) -> None:
        """Lance le rafraîchissement du statut en tâche de fond."""
        self._refresh_status_worker()

    @work(thread=True)
    def _refresh_status_worker(self) -> None:
        """Lit l'état filesystem sans bloquer l'UI."""
        if not self._installer:
            return
        status = self._installer.status()
        self.call_from_thread(
            self.query_one(InstallStatusPanel).refresh_status, status
        )

    def _do_install(self) -> None:
        """Lance l'installation après confirmation si des fichiers existent."""
        if not self._installer:
            return
        status = self._installer.status()

        if status["all_installed"]:
            # Déjà installé → propose mise à jour
            self.app.push_screen(
                ConfirmDialog(
                    title="Mise à jour",
                    message=(
                        "Tous les composants sont déjà installés.\n"
                        "Voulez-vous forcer la mise à jour ?"
                    ),
                ),
                callback=self._on_confirm_install,
            )
        else:
            self._run_install()

    def _on_confirm_install(self, confirmed: bool) -> None:
        if confirmed:
            self._run_install()

    @work(thread=True)
    def _run_install(self) -> None:
        """Exécute install_all() dans un thread — log temps réel via runner."""
        loading = self.query_one("#loading", LoadingIndicator)
        self.call_from_thread(setattr, loading, "styles.display", "block")

        try:
            result = self._installer.install_all()
            self.call_from_thread(self._show_result, result)
        finally:
            self.call_from_thread(setattr, loading, "styles.display", "none")
            self.call_from_thread(self._do_refresh)

    def _do_uninstall(self) -> None:
        """Demande confirmation avant désinstallation."""
        if not self._installer:
            return
        self.app.push_screen(
            ConfirmDialog(
                title="Désinstallation",
                message=(
                    "Supprimer le fichier cron, logrotate et le service zbm-startup ?\n"
                    "Cette action est réversible (relancer install_all)."
                ),
                danger=True,
            ),
            callback=self._on_confirm_uninstall,
        )

    def _on_confirm_uninstall(self, confirmed: bool) -> None:
        if confirmed:
            self._run_uninstall()

    @work(thread=True)
    def _run_uninstall(self) -> None:
        loading = self.query_one("#loading", LoadingIndicator)
        self.call_from_thread(setattr, loading, "styles.display", "block")
        try:
            result = self._installer.uninstall_all()
            self.call_from_thread(self._show_result, result)
        finally:
            self.call_from_thread(setattr, loading, "styles.display", "none")
            self.call_from_thread(self._do_refresh)

    # ── Affichage résultat ────────────────────────────────────────────────────

    def _show_result(self, result: InstallResult) -> None:
        """Affiche le résumé du résultat dans le CommandLog."""
        cmd_log = self.query_one("#cmd-log", CommandLog)
        cmd_log.append("")
        cmd_log.append("─" * 60)
        cmd_log.append(result.summary)
        for sub in result.sub:
            cmd_log.append(f"  {sub.summary}")
        for err in result.errors:
            cmd_log.append(f"  [red]⚠ {err}[/]")
        cmd_log.append("─" * 60)


# =============================================================================
# ENTRÉE CLI (python3 -m fsdeploy install-system)
# =============================================================================

def cli_install(
    mountpoint: str = "/",
    dry_run: bool = False,
    component: str = "all",
) -> int:
    """
    Point d'entrée CLI pour l'installation système.
    Appelé par fsdeploy/core/cli.py sub-commande 'install-system'.

    Returns:
        Code de retour (0 = succès, 1 = erreur).
    """
    import sys

    cfg    = FsDeployConfig.default()
    runner = CommandRunner(dry_run=dry_run)
    inst   = SystemInstaller(cfg, runner, mountpoint=Path(mountpoint))

    print(f"▶ Installation système fsdeploy")
    print(f"  Rootfs   : {mountpoint}")
    print(f"  Init     : {inst.init_system.label}")
    print(f"  Composant: {component}")
    if dry_run:
        print("  [DRY RUN — aucune modification]")
    print()

    fn_map = {
        "all":       inst.install_all,
        "cron":      inst.install_cron,
        "logrotate": inst.install_logrotate,
        "service":   inst.install_service,
        "uninstall": inst.uninstall_all,
        "status":    None,
    }

    if component == "status":
        import json
        status = inst.status()
        print(json.dumps(status, indent=2, default=str))
        return 0

    fn = fn_map.get(component)
    if fn is None:
        print(f"Composant inconnu : {component}", file=sys.stderr)
        print(f"Choix : {', '.join(fn_map)}", file=sys.stderr)
        return 1

    result = fn()

    print(result.summary)
    for sub in result.sub:
        print(f"  {sub.summary}")
    for err in result.errors:
        print(f"  ⚠ {err}", file=sys.stderr)

    return 0 if result.ok else 1
