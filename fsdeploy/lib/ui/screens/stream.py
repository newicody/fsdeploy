"""
fsdeploy.ui.screens.stream — Stream YouTube RTMP, 100% bus events.
"""
import os
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, Label, Log, Static, Switch

IS_FB = os.environ.get("TERM") == "linux"
CHECK, CROSS, WARN = ("[OK]","[!!]","[??]") if IS_FB else ("✅","❌","⚠️")


class StreamScreen(Screen):
    BINDINGS = [
        Binding("s", "start_stream", "Demarrer", show=True),
        Binding("t", "stop_stream", "Arreter", show=True),
        Binding("r", "refresh_status", "Statut", show=True),
        Binding("escape", "app.pop_screen", "Retour", show=False),
    ]
    DEFAULT_CSS = """
    StreamScreen { layout: vertical; overflow-y: auto; }
    #stream-header { height: auto; padding: 1 2; text-style: bold; }
    #stream-status { padding: 0 2; height: 1; color: $text-muted; }
    #stream-live { height: auto; padding: 1 2; margin: 0 1; border: solid $success; }
    #stream-config { height: auto; margin: 0 1; padding: 1 2; border: solid $accent; }
    .cfg-row { height: 3; layout: horizontal; }
    .cfg-row Label { width: 20; padding: 1 0; }
    .cfg-row Input { width: 1fr; }
    #command-log { height: 10; margin: 0 1; border: solid $primary-background; padding: 0 1; }
    #action-buttons { height: 3; padding: 0 2; layout: horizontal; }
    #action-buttons Button { margin: 0 1; }
    """
    def __init__(self, **kw):
        super().__init__(**kw); self.name = "stream"; self._running = False; self._pid = ""
    @property
    def bridge(self): return getattr(self.app, "bridge", None)

    def compose(self) -> ComposeResult:
        yield Static("Stream YouTube", id="stream-header")
        yield Static("Statut : arrete", id="stream-status")
        with Vertical(id="stream-live"):
            yield Label("Stream en direct", classes="info-label")
            yield Label("Arrete", id="live-detail")
        with Vertical(id="stream-config"):
            yield Label("Configuration stream")
            with Horizontal(classes="cfg-row"):
                yield Label("Cle YouTube :"); yield Input(id="input-key", password=True)
            with Horizontal(classes="cfg-row"):
                yield Label("Resolution :"); yield Input(id="input-res", value="1920x1080")
            with Horizontal(classes="cfg-row"):
                yield Label("FPS :"); yield Input(id="input-fps", value="30")
            with Horizontal(classes="cfg-row"):
                yield Label("Bitrate :"); yield Input(id="input-bitrate", value="4500k")
            with Horizontal(classes="cfg-row"):
                yield Label("Source :"); yield Input(id="input-source", value="/dev/fb0")
        yield Log(id="command-log", highlight=True, auto_scroll=True)
        with Horizontal(id="action-buttons"):
            yield Button("Demarrer", variant="primary", id="btn-start")
            yield Button("Arreter", variant="error", id="btn-stop", disabled=True)
            yield Button("Statut", variant="default", id="btn-status")

    def on_mount(self):
        cfg = getattr(self.app, "config", None)
        if cfg:
            self.query_one("#input-key", Input).value = cfg.get("stream.youtube_key", "")
            self.query_one("#input-res", Input).value = cfg.get("stream.resolution", "1920x1080")
            self.query_one("#input-fps", Input).value = str(cfg.get("stream.fps", 30))
            self.query_one("#input-bitrate", Input).value = cfg.get("stream.bitrate", "4500k")
            self.query_one("#input-source", Input).value = cfg.get("stream.input", "/dev/fb0")
        self.action_refresh_status()

    def on_button_pressed(self, e):
        bid = e.button.id or ""
        if bid == "btn-start": self.action_start_stream()
        elif bid == "btn-stop": self.action_stop_stream()
        elif bid == "btn-status": self.action_refresh_status()

    def action_start_stream(self):
        if not self.bridge: return
        key = self.query_one("#input-key", Input).value.strip()
        if not key: self.notify("Cle YouTube requise.", severity="warning"); return
        self.bridge.emit("stream.start",
            stream_key=key,
            resolution=self.query_one("#input-res", Input).value.strip(),
            fps=int(self.query_one("#input-fps", Input).value.strip() or 30),
            bitrate=self.query_one("#input-bitrate", Input).value.strip(),
            input=self.query_one("#input-source", Input).value.strip(),
            callback=self._on_started)
        self._log("-> stream.start")

    def _on_started(self, t):
        if t.status == "completed":
            r = t.result or {}
            self._running = True; self._pid = str(r.get("pid",""))
            self._safe(lambda: self._update_live(r))
            self._slog(f"{CHECK} Stream demarre (PID {self._pid})")
        else:
            self._slog(f"{CROSS} {t.error}")

    def action_stop_stream(self):
        if not self.bridge: return
        self.bridge.emit("stream.stop", callback=self._on_stopped)
        self._log("-> stream.stop")

    def _on_stopped(self, t):
        self._running = False; self._pid = ""
        self._safe(lambda: self._update_live({}))
        self._slog(f"{CHECK} Stream arrete" if t.status == "completed"
                   else f"{CROSS} {t.error}")

    def action_refresh_status(self):
        if not self.bridge: return
        self.bridge.emit("stream.status", callback=self._on_status)

    def _on_status(self, t):
        if t.status == "completed":
            r = t.result or {}
            self._running = r.get("running", False)
            self._pid = str(r.get("pid",""))
            self._safe(lambda: self._update_live(r))

    def _update_live(self, info):
        if self._running:
            self.query_one("#live-detail", Label).update(
                f"EN DIRECT — PID {self._pid}  "
                f"{info.get('resolution','?')}  {info.get('fps','')}fps  "
                f"{info.get('bitrate','')}")
            self.query_one("#stream-status", Static).update(f"Statut : {CHECK} en direct")
            self.query_one("#btn-start", Button).disabled = True
            self.query_one("#btn-stop", Button).disabled = False
        else:
            self.query_one("#live-detail", Label).update("Arrete")
            self.query_one("#stream-status", Static).update("Statut : arrete")
            self.query_one("#btn-start", Button).disabled = False
            self.query_one("#btn-stop", Button).disabled = True

    def update_from_snapshot(self, s):
        for e in s.get("recent_events", []):
            if "stream" in e.get("name", ""): self._log(f"  [bus] {e['name']}")

    def _log(self, m):
        try: self.query_one("#command-log", Log).write_line(m)
        except: pass
    def _slog(self, m):
        try: self.app.call_from_thread(self._log, m)
        except: self._log(m)
    def _safe(self, fn):
        try: self.app.call_from_thread(fn)
        except: fn()
