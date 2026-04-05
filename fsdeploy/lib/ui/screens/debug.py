"""
fsdeploy.ui.screens.debug — Debug / exec / logs / stats, 100% bus events.
"""
import os, time
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, Label, Log, Static

IS_FB = os.environ.get("TERM") == "linux"
CHECK, CROSS = ("[OK]","[!!]") if IS_FB else ("✅","❌")

class DebugScreen(Screen):
    BINDINGS = [
        Binding("escape", "app.pop_screen", "Retour", show=False),
    ]
    DEFAULT_CSS = """
    DebugScreen { layout: vertical; }
    #debug-header { height: auto; padding: 1 2; text-style: bold; }
    #stats-panel { height: auto; padding: 1 2; margin: 0 1; border: solid $accent; }
    #exec-row { height: 3; padding: 0 2; layout: horizontal; }
    #exec-row Input { width: 1fr; margin: 0 1; }
    #exec-row Button { margin: 0 1; }
    #output-log { height: 1fr; margin: 0 1; border: solid $primary-background; padding: 0 1; }
    #action-buttons { height: 3; padding: 0 2; layout: horizontal; }
    #action-buttons Button { margin: 0 1; }
    """
    def __init__(self, **kw):
        super().__init__(**kw)

    @property
    def bridge(self): return getattr(self.app, "bridge", None)

    def compose(self) -> ComposeResult:
        yield Static("Debug / Diagnostique", id="debug-header")
        with Vertical(id="stats-panel"):
            yield Label("Runtime", classes="info-label")
            yield Label("...", id="stats-detail")
        with Horizontal(id="exec-row"):
            yield Label("Commande :")
            yield Input(id="input-cmd", placeholder="zpool status / zfs list / uname -a ...")
            yield Button("Exec", variant="primary", id="btn-exec")
            yield Button("Exec sudo", variant="warning", id="btn-exec-sudo")
        yield Log(id="output-log", highlight=True, auto_scroll=True)
        with Horizontal(id="action-buttons"):
            yield Button("Dump config", id="btn-dump-config")
            yield Button("Dump scheduler", id="btn-dump-scheduler")
            yield Button("Dump store", id="btn-dump-store")
            yield Button("Effacer log", id="btn-clear")

    def on_mount(self):
        self._refresh_stats()

    def on_button_pressed(self, e):
        bid = e.button.id or ""
        if bid == "btn-exec": self._exec_cmd(sudo=False)
        elif bid == "btn-exec-sudo": self._exec_cmd(sudo=True)
        elif bid == "btn-dump-config": self._dump_config()
        elif bid == "btn-dump-scheduler": self._dump_scheduler()
        elif bid == "btn-dump-store": self._dump_store()
        elif bid == "btn-clear":
            try: self.query_one("#output-log", Log).clear()
            except: pass

    def _exec_cmd(self, sudo: bool = False):
        cmd = self.query_one("#input-cmd", Input).value.strip()
        if not cmd: return
        if not self.bridge: return
        self._log(f"$ {'sudo ' if sudo else ''}{cmd}")
        self.bridge.emit("debug.exec", cmd=cmd, sudo=sudo,
                         callback=self._on_exec_done)

    def _on_exec_done(self, t):
        if t.status == "completed":
            r = t.result or {}
            out = r.get("stdout", "")
            err = r.get("stderr", "")
            rc = r.get("returncode", "?")
            if out:
                for line in out.splitlines():
                    self._slog(f"  {line}")
            if err:
                for line in err.splitlines():
                    self._slog(f"  [stderr] {line}")
            self._slog(f"  [exit {rc}]")
        else:
            self._slog(f"{CROSS} {t.error}")

    def _dump_config(self):
        cfg = getattr(self.app, "config", None)
        if not cfg:
            self._log("Config non disponible"); return
        self._log(f"=== Config : {getattr(cfg, 'path', '?')} ===")
        for section in ("env", "pool", "kernel", "initramfs", "overlay",
                         "zbm", "stream", "scheduler", "log"):
            val = cfg.get(section, {})
            if isinstance(val, dict):
                for k, v in val.items():
                    self._log(f"  {section}.{k} = {v}")
            else:
                self._log(f"  {section} = {val}")

    def _dump_scheduler(self):
        runtime = getattr(self.app, "runtime", None)
        if not runtime:
            self._log("Runtime non disponible"); return
        self._log(f"=== Scheduler ===")
        self._log(f"  {runtime.summary()}")
        executor = getattr(self.app, "executor", None)
        if executor:
            self._log(f"  executor pending: {executor.pending_count}")

        # Bridge stats
        bridge = self.bridge
        if bridge:
            self._log(f"  bridge pending: {bridge.pending_count}")
            self._log(f"  bridge active: {bridge.active_events}")

    def _dump_store(self):
        store = getattr(self.app, "store", None)
        if not store:
            self._log("HuffmanStore non disponible"); return
        stats = store.stats()
        self._log(f"=== HuffmanStore ===")
        self._log(f"  Total records : {stats['total_records']}")
        self._log(f"  Total bytes   : {stats['total_bytes']}")
        self._log(f"  Compression   : {stats['compression_ratio']:.3f}")
        self._log(f"  Vocabulaire   : {stats['codec_vocabulary']} tokens")
        for name, info in stats["tables"].items():
            self._log(f"  {name:12s}: {info['records']:5d} records, {info['bytes']:6d} B")
        self._log(f"  Top tokens :")
        for tok, freq, code in stats.get("top_tokens", [])[:5]:
            self._log(f"    {tok:30s} freq={freq:4d} code={code}")

    def _refresh_stats(self):
        lines = []
        runtime = getattr(self.app, "runtime", None)
        if runtime:
            lines.append(f"Scheduler: {runtime.summary()}")
        store = getattr(self.app, "store", None)
        if store:
            s = store.stats()
            lines.append(f"Store: {s['total_records']} records, "
                         f"ratio={s['compression_ratio']:.3f}")
        bridge = self.bridge
        if bridge:
            lines.append(f"Bridge: {bridge.pending_count} pending")
        try:
            self.query_one("#stats-detail", Label).update(
                "\n".join(lines) if lines else "N/A")
        except: pass

    def update_from_snapshot(self, s):
        self._refresh_stats()

    def _log(self, m):
        try: self.query_one("#output-log", Log).write_line(m)
        except: pass
    def _slog(self, m):
        try: self.app.call_from_thread(self._log, m)
        except: self._log(m)
