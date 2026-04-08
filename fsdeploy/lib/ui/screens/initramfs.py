"""
fsdeploy.ui.screens.initramfs
===============================
Ecran de gestion des initramfs — 100% bus events.

Operations :
  bridge.emit("initramfs.list", boot_path="/mnt/boot")
  bridge.emit("initramfs.build", kernel_version="6.12.0",
              init_type="zbm", method="dracut", compress="zstd")
  bridge.emit("boot.init.generate", init_type="stream",
              boot_pool="boot_pool", stream_key="XXXX")

Types d'init :
  zbm     — lance ZFSBootMenu standard
  minimal — monte ZFS + pivot_root, pas de ZBM
  stream  — reseau + Python + YouTube stream, sans rootfs
  custom  — script init fourni par l'utilisateur

Methodes de construction :
  dracut — utilise dracut avec modules configurables
  cpio   — construction manuelle via cpio (fallback)
"""

import os
from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import (
    Button, DataTable, Input, Label, Log, Rule,
    Select, Static, Switch,
)

IS_FB = os.environ.get("TERM") == "linux"
CHECK = "[OK]" if IS_FB else "✅"
CROSS = "[!!]" if IS_FB else "❌"
WARN  = "[??]" if IS_FB else "⚠️"
ARROW = "->" if IS_FB else "→"
STAR  = "*" if IS_FB else "★"

INIT_TYPES = [
    ("zbm", "ZFSBootMenu — boot standard"),
    ("minimal", "Minimal — ZFS + pivot_root"),
    ("stream", "Stream — reseau + YouTube, sans rootfs"),
    ("custom", "Custom — script /init fourni"),
]

BUILD_METHODS = [
    ("dracut", "Dracut (recommande)"),
    ("cpio", "CPIO manuel (fallback)"),
]

COMPRESS_OPTIONS = [
    ("zstd", "Zstandard (rapide)"),
    ("xz", "XZ (compact)"),
    ("gzip", "Gzip (compatible)"),
    ("lz4", "LZ4 (tres rapide)"),
]

class InitramfsScreen(Screen):

    BINDINGS = [
        Binding("r", "refresh", "Rafraichir", show=True),
        Binding("b", "build", "Construire", show=True),
        Binding("g", "generate_init", "Generer /init", show=True),
        Binding("enter", "next_step", "Suivant", show=True),
        Binding("escape", "app.pop_screen", "Retour", show=False),
    ]

    DEFAULT_CSS = """
    InitramfsScreen { layout: vertical; overflow-y: auto; }
    #initramfs-header { height: auto; padding: 1 2; text-style: bold; }
    #initramfs-status { padding: 0 2; height: 1; color: $text-muted; }

    #images-section { height: auto; max-height: 30%; margin: 0 1;
                      border: solid $primary; padding: 0 1; }

    #build-section { height: auto; margin: 0 1; padding: 1 2;
                     border: solid $accent; }
    .build-row { height: 3; layout: horizontal; padding: 0 0; }
    .build-row Label { width: 20; padding: 1 0; }
    .build-row Select { width: 1fr; }
    .build-row Input { width: 1fr; }

    #stream-options { height: auto; margin: 0 1; padding: 1 2;
                      border: solid $warning; }

    #command-log { height: 8; margin: 0 1; border: solid $primary-background;
                   padding: 0 1; }
    #action-buttons { height: 3; padding: 0 2; layout: horizontal; }
    #action-buttons Button { margin: 0 1; }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._images: list[dict] = []
        self._boot_path: str = "/boot"
        self._kernel_version: str = ""
        self._building: bool = False

    @property
    def bridge(self):
        return getattr(self.app, "bridge", None)

    # ── Compose ─────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Static("Gestion des initramfs", id="initramfs-header")
        yield Static("Statut : chargement...", id="initramfs-status")

        # Images existantes
        with Vertical(id="images-section"):
            yield Label("Images initramfs existantes")
            yield DataTable(id="images-table")

        # Options de construction
        with Vertical(id="build-section"):
            yield Label("Construction d'un initramfs", classes="info-label")

            with Horizontal(classes="build-row"):
                yield Label("Type d'init :")
                yield Select(
                    [(label, value) for value, label in INIT_TYPES],
                    value="zbm", id="select-init-type",
                )

            with Horizontal(classes="build-row"):
                yield Label("Methode :")
                yield Select(
                    [(label, value) for value, label in BUILD_METHODS],
                    value="dracut", id="select-method",
                )

            with Horizontal(classes="build-row"):
                yield Label("Compression :")
                yield Select(
                    [(label, value) for value, label in COMPRESS_OPTIONS],
                    value="zstd", id="select-compress",
                )

            with Horizontal(classes="build-row"):
                yield Label("Kernel :")
                yield Input(placeholder="version (ex: 6.12.0) — vide = actif",
                            id="input-kernel-version")

            with Horizontal(classes="build-row"):
                yield Label("Modules extra :")
                yield Input(placeholder="module1, module2 (optionnel)",
                            id="input-extra-modules")

            with Horizontal(classes="build-row"):
                yield Label("Drivers extra :")
                yield Input(placeholder="driver1, driver2 (optionnel)",
                            id="input-extra-drivers")

        # Options stream (visibles seulement si type=stream)
        with Vertical(id="stream-options"):
            yield Label("Options stream YouTube", classes="info-label")

            with Horizontal(classes="build-row"):
                yield Label("Cle YouTube :")
                yield Input(placeholder="XXXX-XXXX-XXXX-XXXX",
                            password=True, id="input-stream-key")

            with Horizontal(classes="build-row"):
                yield Label("Boot pool :")
                yield Input(placeholder="boot_pool", id="input-boot-pool")

            with Horizontal(classes="build-row"):
                yield Label("Boot dataset :")
                yield Input(placeholder="boot_pool/boot",
                            id="input-boot-dataset")

        yield Log(id="command-log", highlight=True, auto_scroll=True)

        with Horizontal(id="action-buttons"):
            yield Button("Rafraichir", variant="default", id="btn-refresh")
            yield Button("Construire", variant="primary", id="btn-build")
            yield Button("Generer /init", variant="warning", id="btn-gen-init")
            yield Button(f"Suivant {ARROW}", variant="success", id="btn-next")

    def on_mount(self) -> None:
        dt = self.query_one("#images-table", DataTable)
        dt.add_columns("", "Fichier", "Version", "Taille")
        dt.cursor_type = "row"

        # Charger depuis la config
        cfg = getattr(self.app, "config", None)
        if cfg:
            bp = cfg.get("pool.boot_mount", "")
            if bp:
                self._boot_path = bp
            kv = cfg.get("kernel.version", "")
            if kv:
                self._kernel_version = kv
                self.query_one("#input-kernel-version", Input).value = kv

            # Stream
            sk = cfg.get("stream.youtube_key", "")
            if sk:
                self.query_one("#input-stream-key", Input).value = sk
            bpool = cfg.get("pool.boot_pool", "boot_pool")
            self.query_one("#input-boot-pool", Input).value = bpool
            self.query_one("#input-boot-dataset", Input).value = f"{bpool}/boot"

            # Type initramfs depuis config
            init_type = cfg.get("initramfs.type", "zbm")
            try:
                self.query_one("#select-init-type", Select).value = init_type
            except Exception:
                pass

        self._refresh_list()

    # ── Rafraichir ──────────────────────────────────────────────────

    def _refresh_list(self) -> None:
        if not self.bridge:
            return
        self.bridge.emit("initramfs.list",
                         boot_path=self._boot_path,
                         callback=self._on_list_done)
        self._log(f"  -> initramfs.list({self._boot_path})")

    def _on_list_done(self, ticket) -> None:
        if ticket.status == "completed" and isinstance(ticket.result, list):
            self._images = ticket.result
            self._safe_call(self._refresh_table)
            self._safe_call(lambda: self._set_status(
                f"{CHECK} {len(self._images)} images trouvees"))
        elif ticket.status == "failed":
            self._safe_call(lambda: self._set_status(
                f"{CROSS} {ticket.error}"))

    def _refresh_table(self) -> None:
        dt = self.query_one("#images-table", DataTable)
        dt.clear()
        for img in self._images:
            active = STAR if img.get("active") else ""
            size_mb = img.get("size", 0) / (1024 * 1024)
            dt.add_row(active, img.get("file", "?"),
                       img.get("version", "?"), f"{size_mb:.1f} MB")

    # ── Buttons ─────────────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "btn-refresh":
            self._refresh_list()
        elif bid == "btn-build":
            self.action_build()
        elif bid == "btn-gen-init":
            self.action_generate_init()
        elif bid == "btn-next":
            self.action_next_step()

    # ── Construction ────────────────────────────────────────────────

    def action_build(self) -> None:
        """Construit un initramfs via le bus."""
        if self._building or not self.bridge:
            return

        init_type = self.query_one("#select-init-type", Select).value
        method = self.query_one("#select-method", Select).value
        compress = self.query_one("#select-compress", Select).value
        kver = self.query_one("#input-kernel-version", Input).value.strip()
        extra_modules = self.query_one("#input-extra-modules", Input).value.strip()
        extra_drivers = self.query_one("#input-extra-drivers", Input).value.strip()

        if not kver:
            kver = self._kernel_version
        if not kver:
            self.notify("Specifiez une version de kernel.", severity="warning")
            return

        self._building = True
        self._log(f"=== Construction initramfs ===")
        self._log(f"  type={init_type}  method={method}  compress={compress}")
        self._log(f"  kernel={kver}")

        params = {
            "kernel_version": kver,
            "init_type": init_type,
            "method": method,
            "compress": compress,
            "force": True,
        }
        if extra_modules:
            params["extra_modules"] = [m.strip() for m in extra_modules.split(",")]
        if extra_drivers:
            params["extra_drivers"] = [d.strip() for d in extra_drivers.split(",")]

        # Pour le type stream, ajouter les params init
        if init_type == "stream":
            params["init_file"] = ""  # sera genere
            params["stream_key"] = self.query_one(
                "#input-stream-key", Input).value.strip()

        self.bridge.emit("initramfs.build", callback=self._on_build_done,
                         **params)
        self._log(f"  -> initramfs.build")
        self.notify("Construction lancee (peut prendre plusieurs minutes).",
                    timeout=10)

    def _on_build_done(self, ticket) -> None:
        self._building = False
        if ticket.status == "completed":
            result = ticket.result or {}
            path = result.get("path", "?")
            size = result.get("size", 0)
            size_mb = size / (1024 * 1024)
            self._safe_log(f"{CHECK} Initramfs construit : {path} ({size_mb:.1f} MB)")
            self._safe_call(self._refresh_list)
            self._safe_call(lambda: self._save_to_config(result))
        else:
            self._safe_log(f"{CROSS} Erreur construction : {ticket.error}")

    # ── Generation du script /init ──────────────────────────────────

    def action_generate_init(self) -> None:
        """Genere le script /init pour l'initramfs via le bus."""
        if not self.bridge:
            return

        init_type = self.query_one("#select-init-type", Select).value

        params = {"init_type": init_type}

        if init_type == "stream":
            params["stream_key"] = self.query_one(
                "#input-stream-key", Input).value.strip()

        if init_type in ("minimal", "stream"):
            params["boot_pool"] = self.query_one(
                "#input-boot-pool", Input).value.strip() or "boot_pool"
            params["boot_dataset"] = self.query_one(
                "#input-boot-dataset", Input).value.strip()

            # Overlay
            cfg = getattr(self.app, "config", None)
            if cfg:
                params["overlay_pool"] = cfg.get("overlay.pool", "fast_pool")
                params["overlay_dataset"] = cfg.get("overlay.dataset", "")
                params["rootfs_sfs"] = cfg.get("overlay.rootfs_sfs",
                                                "images/rootfs.sfs")

        self.bridge.emit("boot.init.generate", callback=self._on_init_gen,
                         **params)
        self._log(f"  -> boot.init.generate(type={init_type})")

    def _on_init_gen(self, ticket) -> None:
        if ticket.status == "completed":
            result = ticket.result or {}
            self._safe_log(f"{CHECK} /init genere : {result.get('output', '?')}")
        else:
            self._safe_log(f"{CROSS} Generation /init : {ticket.error}")

    def action_refresh(self) -> None:
        self._refresh_list()

    def action_next_step(self) -> None:
        if hasattr(self.app, "navigate_next"):
            self.app.navigate_next()

    # ── Config ──────────────────────────────────────────────────────

    def _save_to_config(self, build_result: dict) -> None:
        cfg = getattr(self.app, "config", None)
        if not cfg:
            return

        init_type = self.query_one("#select-init-type", Select).value
        method = self.query_one("#select-method", Select).value
        compress = self.query_one("#select-compress", Select).value

        # Chemin relatif au boot_mount
        path = build_result.get("path", "")
        if path and self._boot_path and path.startswith(self._boot_path):
            path = path[len(self._boot_path):].lstrip("/")

        cfg.set("initramfs.active", path)
        cfg.set("initramfs.type", init_type)
        cfg.set("initramfs.method", method)
        cfg.set("initramfs.compress", compress)

        try:
            cfg.save()
        except Exception:
            pass

    # ── Snapshot refresh ────────────────────────────────────────────

    def update_from_snapshot(self, snapshot: dict) -> None:
        for evt in snapshot.get("recent_events", []):
            name = evt.get("name", "")
            if "initramfs" in name or "boot.init" in name:
                self._log(f"  [bus] {name}")

    # ── UI helpers ──────────────────────────────────────────────────

    def _log(self, msg: str) -> None:
        try:
            self.query_one("#command-log", Log).write_line(msg)
        except Exception:
            pass

    def _safe_log(self, msg: str) -> None:
        try:
            self.app.call_from_thread(self._log, msg)
        except Exception:
            self._log(msg)

    def _set_status(self, text: str) -> None:
        try:
            self.query_one("#initramfs-status", Static).update(
                f"Statut : {text}")
        except Exception:
            pass

    def _safe_call(self, fn) -> None:
        try:
            self.app.call_from_thread(fn)
        except Exception:
            fn()
