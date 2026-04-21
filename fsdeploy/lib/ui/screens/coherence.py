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
from textual.on import on

IS_FB = os.environ.get("TERM") == "linux"
CHECK, CROSS, WARN, ARROW = ("[OK]","[!!]","[??]","->") if IS_FB else ("✅","❌","⚠️","→")

class CoherenceScreen(Screen):

    BINDINGS = [
        Binding("r", "run_check", "Verifier", show=True),
        Binding("q", "run_quick_check", "Verif rapide", show=True),
        Binding("enter", "next_step", "Suivant", show=True),
        Binding("e", "export_report", "Exporter", show=True),
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
    #detail-section { height: auto; padding: 1 2; margin: 0 1; border: dashed $primary; }
    #command-log { height: 6; margin: 0 1; border: solid $primary-background;
                   padding: 0 1; }
    #action-buttons { height: 3; padding: 0 2; layout: horizontal; }
    #action-buttons Button { margin: 0 1; }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._checks: list[dict] = []
        self._passed: bool = False
        self._check_running: bool = False

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

        with Vertical(id="detail-section"):
            yield Label("Détail de la vérification")
            yield Static("Sélectionnez une ligne.", id="detail-text")

        yield Log(id="command-log", highlight=True, auto_scroll=True)

        with Horizontal(id="action-buttons"):
            yield Button("Verifier", variant="primary", id="btn-check")
            yield Button("Rapide", variant="default", id="btn-quick")
            yield Button(f"Suivant {ARROW}", variant="success", id="btn-next",
                         disabled=True)

    def on_mount(self) -> None:
        from fsdeploy.lib.ui.bridge import SchedulerBridge
        self.bridge = SchedulerBridge.default()
        dt = self.query_one("#checks-table", DataTable)
        dt.add_columns("", "Verification", "Resultat", "Severite")
        dt.cursor_type = "row"
        self.action_run_check()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "btn-check": self.action_run_check()
        elif bid == "btn-next": self.action_next_step()
        elif bid == "btn-quick": self.action_run_quick_check()

    def action_run_check(self) -> None:
        if not self.bridge: return
        if self._check_running:
            self._log("Une vérification est déjà en cours.")
            return
        self._check_running = True
        cfg = getattr(self.app, "config", None)
        boot_path = cfg.get("pool.boot_mount", "/boot") if cfg else "/boot"
        active_preset = cfg.get("presets.active", "") if cfg else ""
        preset_data = {}
        if active_preset and cfg:
            preset_data = dict(cfg.get(f"presets.{active_preset}", {}))
        # Extraire pools et snapshots du preset ou de la config
        pools = preset_data.get("pools", [])
        if not pools and cfg:
            pools = cfg.get("pool.import", [])
        snapshots = preset_data.get("snapshots", [])
        # Option ZBM preflight (activé par défaut)
        run_zbm_preflight = cfg.get("zbm.preflight", True) if cfg else True

        # Extraire les paramètres noyau requis
        required_kernel_params = preset_data.get("required_kernel_params", [])
        if not required_kernel_params and cfg:
            required_kernel_params = cfg.get("kernel.required_params", [])
        kernel_version = cfg.get("kernel.version", "") if cfg else ""
        snapshot_max_age_days = preset_data.get("snapshot_max_age_days")
        if snapshot_max_age_days is None and cfg:
            snapshot_max_age_days = cfg.get("snapshot.max_age_days")
        root_dataset = preset_data.get("root_dataset", "")
        if not root_dataset and cfg:
            root_dataset = cfg.get("dataset.root", "")

        # Construire les paramètres pour la vérification de cohérence
        params = {
            "boot_path": boot_path,
            "preset": preset_data,
            "pools": pools,
            "snapshots": snapshots,
            "run_zbm_preflight": run_zbm_preflight,
            "required_kernel_params": required_kernel_params,
            "kernel_version": kernel_version,
            "snapshot_max_age_days": snapshot_max_age_days,
            "root_dataset": root_dataset,
        }
        # Ajouter les paramètres facultatifs de configuration
        if cfg:
            params["efi_device"] = cfg.get("partition.efi_device", "")
            params["efi_mount"] = cfg.get("partition.efi_mount", "")
            params["zbm_efi_path"] = cfg.get("zbm.efi_path", "")
            params["zbm_install_method"] = cfg.get("zbm.install_method", "")
            params["zbm_cmdline"] = cfg.get("zbm.cmdline", "")
            params["kernel_active"] = cfg.get("kernel.active", "")
            params["initramfs_active"] = cfg.get("initramfs.active", "")
            params["mounts"] = cfg.get("mounts", {})
            # Autres paramètres potentiellement utiles
            params["staging_dir"] = cfg.get("kernel.staging_dir", "")
            params["zbm_bootfs"] = cfg.get("zbm.bootfs", "")
            params["zbm_config_yaml"] = cfg.get("zbm.config_yaml", "")
            params["zbm_image_dir"] = cfg.get("zbm.image_dir", "")
            params["run_scheduler_check"] = cfg.get("scheduler.check", True)

        self._set_status("Verification en cours...")
        self.query_one("#btn-check", Button).disabled = True
        self.query_one("#btn-quick", Button).disabled = True
        self.bridge.emit("coherence.check",
                         callback=self._on_check_done,
                         **params)
        self._log("-> coherence.check")
        # Migration vers SchedulerBridge terminée

    def _on_check_done(self, ticket) -> None:
        self._check_running = False
        self.query_one("#btn-check", Button).disabled = False
        self.query_one("#btn-quick", Button).disabled = False
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
            error_msg = getattr(ticket, 'error', 'unknown error')
            self._safe_call(lambda: self._set_status(f"{CROSS} {error_msg}"))
            self._safe_call(lambda: self._log(f"Ticket status: {ticket.status}"))

    def _refresh_display(self) -> None:
        dt = self.query_one("#checks-table", DataTable)
        dt.clear()
        for idx, c in enumerate(self._checks):
            icon = CHECK if c.get("passed") else (
                CROSS if c.get("severity") == "error" else WARN)
            dt.add_row(icon, c.get("name","?"),
                       c.get("message","")[:60], c.get("severity","?"),
                       key=str(idx))

        icon = CHECK if self._passed else CROSS
        self._set_status(f"{icon} {'Systeme coherent' if self._passed else 'Erreurs detectees'}")
        self.query_one("#btn-next", Button).disabled = not self._passed

    def _set_summary(self, text: str) -> None:
        try: self.query_one("#summary-label", Label).update(text)
        except Exception: pass

    def action_run_quick_check(self) -> None:
        """Lance une vérification rapide (uniquement les vérifications critiques)."""
        if not self.bridge: return
        if self._check_running:
            self._log("Une vérification est déjà en cours.")
            return
        self._check_running = True
        cfg = getattr(self.app, "config", None)
        boot_path = cfg.get("pool.boot_mount", "/boot") if cfg else "/boot"
        active_preset = cfg.get("presets.active", "") if cfg else ""
        preset_data = {}
        if active_preset and cfg:
            preset_data = dict(cfg.get(f"presets.{active_preset}", {}))
        pools = preset_data.get("pools", [])
        if not pools and cfg:
            pools = cfg.get("pool.import", [])
        mounts = cfg.get("mounts", {}) if cfg else {}
        # Paramètres minimum
        params = {
            "boot_path": boot_path,
            "preset": preset_data,
            "pools": pools,
            "mounts": mounts,
            "quick_mode": True,
        }
        self._set_status("Vérification rapide en cours...")
        self.query_one("#btn-quick", Button).disabled = True
        self.query_one("#btn-check", Button).disabled = True
        self.bridge.emit("coherence.quick",
                         callback=self._on_check_done,
                         **params)
        self._log("-> coherence.quick")

    def action_next_step(self) -> None:
        if not self._passed:
            self.notify("Corrigez les erreurs d'abord.", severity="warning")
            return
        if hasattr(self.app, "navigate_next"): self.app.navigate_next()

    def action_export_report(self) -> None:
        """Exporte le rapport de vérification dans un fichier JSON."""
        import json
        from datetime import datetime
        if not self._checks:
            self.notify("Aucune vérification à exporter", severity="warning")
            return
        data = {
            "timestamp": datetime.now().isoformat(),
            "passed": self._passed,
            "checks": self._checks,
        }
        path = f"/tmp/fsdeploy-coherence-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
        try:
            with open(path, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            self.notify(f"Rapport exporté vers {path}", severity="information")
            self._log(f"Export -> {path}")
        except Exception as e:
            self.notify(f"Erreur d'export: {e}", severity="error")

    def update_from_snapshot(self, s: dict) -> None: pass
    def _log(self, m):
        try: self.query_one("#command-log", Log).write_line(m)
        except Exception: pass
    def _safe_call(self, fn):
        try: self.app.call_from_thread(fn)
        except Exception: fn()
    @on(DataTable.RowHighlighted)
    def handle_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        try:
            idx = int(event.row_key.value)
            if 0 <= idx < len(self._checks):
                self._show_detail(self._checks[idx])
        except (ValueError, AttributeError):
            pass

    def _show_detail(self, check: dict) -> None:
        try:
            detail = f"{check.get('name', '?')}\n"
            detail += f"Statut: {'PASS' if check.get('passed') else 'FAIL'}\n"
            detail += f"Sévérité: {check.get('severity', '?')}\n"
            detail += f"Message: {check.get('message', '')}"
            self.query_one("#detail-text", Static).update(detail)
        except Exception:
            pass

    def _set_status(self, t):
        try: self.query_one("#coherence-status", Static).update(f"Statut : {t}")
        except Exception: pass
