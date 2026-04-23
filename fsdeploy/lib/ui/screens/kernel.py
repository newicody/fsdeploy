"""
fsdeploy.ui.screens.kernel — Gestion noyaux, 100% bus events.
Compatible : Textual >=8.2.1 / Rich >=14.3.3
"""
import os
from typing import Any
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Input, Label, Rule, Static, RichLog

IS_FB = os.environ.get("TERM") == "linux"
CHECK, CROSS, WARN, ARROW, STAR = (("[OK]","[!!]","[??]","->","*") if IS_FB else ("✅","❌","⚠️","→","★"))

class KernelScreen(Screen):
    BINDINGS = [
        Binding("r","refresh","Rafraichir",show=True),
        Binding("s","switch_kernel","Activer",show=True),
        Binding("i","install_kernel","Installer .deb",show=True),
        Binding("c","compile_kernel","Compiler",show=True),
        Binding("enter","next_step","Suivant",show=True),
        Binding("escape","app.pop_screen","Retour",show=False),
    ]
    DEFAULT_CSS = """
    KernelScreen { layout: vertical; }
    #kernel-header { height: auto; padding: 1 2; text-style: bold; }
    #kernel-status { padding: 0 2; height: 1; color: $text-muted; }
    #active-kernel { height: auto; padding: 1 2; border: solid $success; margin: 0 1; }
    #kernel-table-container { height: 1fr; margin: 0 1; border: solid $primary; padding: 0 1; }
    #install-row { height: 3; padding: 0 2; layout: horizontal; }
    #install-row Input { width: 1fr; margin: 0 1; }
    #install-row Button { margin: 0 1; }
    #command-log { height: 8; margin: 0 1; border: solid $primary-background; padding: 0 1; }
    #action-buttons { height: 3; padding: 0 2; layout: horizontal; }
    #action-buttons Button { margin: 0 1; }
    """
    def __init__(self, **kw):
        super().__init__(**kw); self._kernels=[]; self._selected_idx=-1; self._boot_path="/boot"
    @property
    def bridge(self): return getattr(self.app,"bridge",None)

    def compose(self) -> ComposeResult:
        yield Static("Gestion des noyaux", id="kernel-header")
        yield Static("Statut : chargement...", id="kernel-status")
        with Vertical(id="active-kernel"):
            yield Label("Kernel actif", classes="info-label")
            yield Label("aucun", id="active-kernel-detail")
        with Vertical(id="kernel-table-container"):
            yield Label("Noyaux disponibles"); yield DataTable(id="kernel-table")
        with Horizontal(id="install-row"):
            yield Label("Source :")
            yield Input(placeholder="/chemin/vers/linux-image.deb ou /usr/src/linux", id="source-input")
            yield Button("Installer", variant="primary", id="btn-install")
            yield Button("Compiler", variant="warning", id="btn-compile")
        yield RichLog(id="command-log", highlight=True, auto_scroll=True, markup=True)
        yield RichLog(id="log-stream", highlight=True, markup=True, max_lines=1000, auto_scroll=True)
        with Horizontal(id="action-buttons"):
            yield Button("Rafraichir", id="btn-refresh")
            yield Button(f"Activer {ARROW}", variant="primary", id="btn-switch")
            yield Button(f"Suivant {ARROW}", variant="success", id="btn-next")

    def on_mount(self):
        from fsdeploy.lib.ui.bridge import SchedulerBridge
        self.bridge = SchedulerBridge.default()
        dt = self.query_one("#kernel-table", DataTable)
        dt.add_columns("","Version","Fichier","Taille","Initramfs","Modules"); dt.cursor_type="row"
        cfg = getattr(self.app,"config",None)
        if cfg:
            bp = cfg.get("pool.boot_mount","")
            if bp: self._boot_path = bp
        # Enregistrer le widget de log
        log_widget = self.query_one("#command-log", RichLog)
        self.bridge.register_log_widget("kernel", "stdout", log_widget)
        # Enregistrer également le widget #log-stream s'il existe
        try:
            log_stream = self.query_one("#log-stream", RichLog)
            self.bridge.register_log_widget("kernel", "stdout", log_stream)
        except Exception:
            pass
        self._refresh_list()

    def _refresh_list(self):
        if not self.bridge: return
        self.bridge.emit("kernel.list", boot_path=self._boot_path, callback=self._on_list)

    def _on_list(self, ticket):
        if ticket.status=="completed" and isinstance(ticket.result, list):
            self._kernels = ticket.result
            self._safe(self._refresh_table)
            active = next((k for k in self._kernels if k.get("active")), None)
            if active: self._safe(lambda: self._set_active(active))
            self._safe(lambda: self._status(f"{CHECK} {len(self._kernels)} noyaux"))

    def _refresh_table(self):
        dt = self.query_one("#kernel-table", DataTable); dt.clear()
        for k in self._kernels:
            sz = k.get("size",0)/(1024*1024)
            dt.add_row(STAR if k.get("active") else "", k.get("version","?"),
                k.get("file","?"), f"{sz:.1f} MB", k.get("initramfs","") or "-",
                CHECK if k.get("has_modules") else "-")

    def _set_active(self, k):
        try:
            self.query_one("#active-kernel-detail", Label).update(
                f"vmlinuz-{k.get('version','?')}   initramfs={k.get('initramfs','aucun')}   "
                f"modules={'oui' if k.get('has_modules') else 'non'}")
        except: pass

    # Textual 8.x: RowHighlighted au lieu de RowSelected
    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted):
        if event.cursor_row is not None: self._selected_idx = event.cursor_row

    def on_button_pressed(self, e):
        bid = e.button.id or ""
        if bid=="btn-refresh": self._refresh_list()
        elif bid=="btn-switch": self.action_switch_kernel()
        elif bid=="btn-install": self.action_install_kernel()
        elif bid=="btn-compile": self.action_compile_kernel()
        elif bid=="btn-next": self.action_next_step()

    def action_refresh(self): self._refresh_list()

    def action_switch_kernel(self):
        if self._selected_idx<0 or self._selected_idx>=len(self._kernels) or not self.bridge:
            self.notify("Selectionnez un kernel.", severity="warning"); return
        v = self._kernels[self._selected_idx].get("version","")
        if not v: return
        self.bridge.emit("kernel.switch", version=v, boot_path=self._boot_path,
            callback=self._on_switch)
        self._log(f"  -> kernel.switch({v})")

    def _on_switch(self, t):
        if t.status=="completed":
            r = t.result or {}; self._slog(f"{CHECK} Kernel {r.get('version','?')} active")
            self._safe(self._refresh_list)
            cfg = getattr(self.app,"config",None)
            if cfg:
                cfg.set("kernel.active", f"vmlinuz-{r.get('version','')}")
                cfg.set("kernel.version", r.get("version",""))
                try: cfg.save()
                except: pass
        else: self._slog(f"{CROSS} Switch: {t.error}")

    def action_install_kernel(self):
        src = self.query_one("#source-input",Input).value.strip()
        if not src or not self.bridge: self.notify("Chemin du .deb requis.", severity="warning"); return
        self.bridge.emit("kernel.install", source=src, boot_path=self._boot_path,
            callback=lambda t: (self._slog(f"{CHECK} Installe") if t.status=="completed"
                else self._slog(f"{CROSS} {t.error}")) or self._safe(self._refresh_list))

    def action_compile_kernel(self):
        src = self.query_one("#source-input",Input).value.strip() or "/usr/src/linux"
        if not self.bridge: return
        self.bridge.emit("kernel.compile", source_dir=src, callback=lambda t:
            self._slog(f"{CHECK} Compile" if t.status=="completed" else f"{CROSS} {t.error}"))
        self.notify("Compilation lancee.", timeout=5)

    def action_next_step(self):
        if hasattr(self.app,"navigate_next"): self.app.navigate_next()
    def update_from_snapshot(self, s): pass
    def _log(self,m):
        try: self.query_one("#command-log",RichLog).write(m)
        except: pass
    def _slog(self,m):
        try: self.app.call_from_thread(self._log,m)
        except: self._log(m)
    def _safe(self,fn):
        try: self.app.call_from_thread(fn)
        except: fn()
    def _status(self,t):
        try: self.query_one("#kernel-status",Static).update(f"Statut : {t}")
        except: pass
