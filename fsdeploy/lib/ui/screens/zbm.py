"""
fsdeploy.ui.screens.zbm — Installation et statut ZFSBootMenu, 100% bus events.
"""
import os
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, Label, Log, Static

IS_FB = os.environ.get("TERM") == "linux"
CHECK, CROSS, WARN, ARROW = ("[OK]","[!!]","[??]","->") if IS_FB else ("✅","❌","⚠️","→")

class ZBMScreen(Screen):
    BINDINGS = [
        Binding("r", "refresh_status", "Statut", show=True),
        Binding("i", "install_zbm", "Installer", show=True),
        Binding("enter", "next_step", "Suivant", show=True),
        Binding("escape", "app.pop_screen", "Retour", show=False),
    ]
    DEFAULT_CSS = """
    ZBMScreen { layout: vertical; overflow-y: auto; }
    #zbm-header { height: auto; padding: 1 2; text-style: bold; }
    #zbm-status { padding: 0 2; height: 1; color: $text-muted; }
    #zbm-info { height: auto; padding: 1 2; margin: 0 1; border: solid $primary; }
    #zbm-config { height: auto; margin: 0 1; padding: 1 2; border: solid $accent; }
    .cfg-row { height: 3; layout: horizontal; }
    .cfg-row Label { width: 18; padding: 1 0; }
    .cfg-row Input { width: 1fr; }
    #command-log { height: 8; margin: 0 1; border: solid $primary-background; padding: 0 1; }
    #action-buttons { height: 3; padding: 0 2; layout: horizontal; }
    #action-buttons Button { margin: 0 1; }
    """
    def __init__(self, **kw):
        super().__init__(**kw)
        self._installed = False; self._efi_entry = False

    @property
    def bridge(self): return getattr(self.app, "bridge", None)

    def compose(self) -> ComposeResult:
        yield Static("ZFSBootMenu", id="zbm-header")
        yield Static("Statut : verification...", id="zbm-status")

        with Vertical(id="zbm-info"):
            yield Label("Statut ZFSBootMenu", classes="info-label")
            yield Label("Verification...", id="zbm-detail")

        with Vertical(id="zbm-config"):
            yield Label("Configuration d'installation")
            with Horizontal(classes="cfg-row"):
                yield Label("Device EFI :")
                yield Input(id="input-efi-device", placeholder="/dev/nvme0n1p1")
            with Horizontal(classes="cfg-row"):
                yield Label("Mount EFI :")
                yield Input(id="input-efi-mount", value="/boot/efi")
            with Horizontal(classes="cfg-row"):
                yield Label("Chemin EFI :")
                yield Input(id="input-efi-path", value="EFI/ZBM/vmlinuz.EFI")
            with Horizontal(classes="cfg-row"):
                yield Label("Cmdline :")
                yield Input(id="input-cmdline",
                            value="quiet loglevel=3 zbm.autosize=0")
            with Horizontal(classes="cfg-row"):
                yield Label("Timeout (s) :")
                yield Input(id="input-timeout", value="3")

        yield Log(id="command-log", highlight=True, auto_scroll=True)

        with Horizontal(id="action-buttons"):
            yield Button("Verifier statut", variant="default", id="btn-status")
            yield Button("Installer ZBM", variant="primary", id="btn-install")
            yield Button(f"Terminer {ARROW}", variant="success", id="btn-finish")

    def on_mount(self):
        from fsdeploy.lib.ui.bridge import SchedulerBridge
        self.bridge = SchedulerBridge.default()
        cfg = getattr(self.app, "config", None)
        if cfg:
            self.query_one("#input-efi-device", Input).value = \
                cfg.get("partition.efi_device", "")
            self.query_one("#input-efi-path", Input).value = \
                cfg.get("zbm.efi_path", "EFI/ZBM/vmlinuz.EFI")
            self.query_one("#input-cmdline", Input).value = \
                cfg.get("zbm.cmdline", "quiet loglevel=3 zbm.autosize=0")
            self.query_one("#input-timeout", Input).value = \
                str(cfg.get("zbm.timeout", 3))
        self.action_refresh_status()

    def on_button_pressed(self, e):
        bid = e.button.id or ""
        if bid == "btn-status": self.action_refresh_status()
        elif bid == "btn-install": self.action_install_zbm()
        elif bid == "btn-finish": self.action_next_step()

    def action_refresh_status(self):
        if not self.bridge: return
        self.bridge.emit("zbm.status", callback=self._on_status)
        self._log("-> zbm.status")

    def _on_status(self, t):
        if t.status == "completed":
            r = t.result or {}
            self._installed = r.get("installed", False)
            self._efi_entry = r.get("efi_entry", False)
            self._safe(lambda: self._update_info(r))
        else:
            self._slog(f"{CROSS} {t.error}")

    def _update_info(self, info):
        lines = []
        if info.get("installed"):
            for p in info.get("paths_found", []):
                lines.append(f"{CHECK} Binaire : {p}")
        else:
            lines.append(f"{CROSS} Binaire ZBM non trouve")

        if info.get("efi_entry"):
            lines.append(f"{CHECK} Entree EFI : {info.get('efi_line', '')}")
        else:
            lines.append(f"{WARN} Pas d'entree EFI ZFSBootMenu")

        detail = "\n".join(lines)
        self.query_one("#zbm-detail", Label).update(detail)

        if self._installed and self._efi_entry:
            self._set_status(f"{CHECK} ZFSBootMenu installe et configure")
        elif self._installed:
            self._set_status(f"{WARN} ZFSBootMenu installe mais pas d'entree EFI")
        else:
            self._set_status(f"{CROSS} ZFSBootMenu non installe")

    def action_install_zbm(self):
        if not self.bridge: return
        self.bridge.emit("zbm.install",
            efi_device=self.query_one("#input-efi-device", Input).value.strip(),
            efi_mount=self.query_one("#input-efi-mount", Input).value.strip(),
            zbm_efi_path=self.query_one("#input-efi-path", Input).value.strip(),
            cmdline=self.query_one("#input-cmdline", Input).value.strip(),
            callback=self._on_install)
        self._log("-> zbm.install")

    def _on_install(self, t):
        if t.status == "completed":
            self._slog(f"{CHECK} ZFSBootMenu installe")
            self._safe(self.action_refresh_status)
            self._save_to_config()
        else:
            self._slog(f"{CROSS} {t.error}")

    def action_next_step(self):
        self._save_to_config()
        self.notify(f"{CHECK} Configuration ZBM sauvegardee. Pret pour le reboot.",
                    timeout=5)
        if hasattr(self.app, "navigate_next"):
            self.app.navigate_next()

    def _save_to_config(self):
        cfg = getattr(self.app, "config", None)
        if not cfg: return
        cfg.set("zbm.efi_path",
                self.query_one("#input-efi-path", Input).value.strip())
        cfg.set("zbm.cmdline",
                self.query_one("#input-cmdline", Input).value.strip())
        cfg.set("zbm.timeout",
                self.query_one("#input-timeout", Input).value.strip())
        try: cfg.save()
        except: pass

    def update_from_snapshot(self, s): pass
    def _log(self, m):
        try: self.query_one("#command-log", Log).write_line(m)
        except: pass
    def _slog(self, m):
        try: self.app.call_from_thread(self._log, m)
        except: self._log(m)
    def _set_status(self, t):
        try: self.query_one("#zbm-status", Static).update(f"Statut : {t}")
        except: pass
    def _safe(self, fn):
        try: self.app.call_from_thread(fn)
        except: fn()
