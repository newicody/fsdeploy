# -*- coding: utf-8 -*-
"""
fsdeploy.ui.screens.mounts
=============================
Montage datasets, 100% bus events.
Compatible : Textual >=8.2.1 / Rich >=14.3.3

ATTENTION :
  - on_mount() est le lifecycle Textual (sans args), pas un callback
  - les callbacks de montage sont nommes _on_mount_done, _on_umount_done
    pour eviter toute collision
  - mount -t zfs <dataset> <mountpoint> (jamais zfs mount)
"""
import json
import os
from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Input, Label, Log, Rule, Static

IS_FB = os.environ.get("TERM") == "linux"
CHECK = "[OK]" if IS_FB else "\u2705"
CROSS = "[!!]" if IS_FB else "\u274c"
WARN  = "[??]" if IS_FB else "\u26a0\ufe0f"
ARROW = "->"  if IS_FB else "\u2192"

MOUNT_PROPOSALS = {
    "boot": "/mnt/boot", "efi": "/mnt/boot/efi", "rootfs": "/mnt/rootfs",
    "kernel": "/mnt/boot", "modules": "/mnt/boot/modules",
    "initramfs": "/mnt/boot", "squashfs": "/mnt/boot/images",
    "overlay": "/mnt/overlay", "python_env": "/mnt/boot/python",
}


class MountsScreen(Screen):

    BINDINGS = [
        Binding("r", "refresh_mounts", "Rafraichir", show=True),
        Binding("m", "mount_selected", "Monter", show=True),
        Binding("u", "umount_selected", "Demonter", show=True),
        Binding("e", "edit_mountpoint", "Modifier", show=True),
        Binding("a", "mount_all", "Tout monter", show=True),
        Binding("v", "verify_all", "Verifier", show=True),
        Binding("o", "overlay_mount", "Overlay", show=True),
        Binding("t", "overlay_teardown", "Teardown", show=True),
        Binding("enter", "next_step", "Suivant", show=True),
        Binding("escape", "app.pop_screen", "Retour", show=False),
    ]

    DEFAULT_CSS = """
    MountsScreen { layout: vertical; }
    #mounts-header { height: auto; padding: 1 2; text-style: bold; }
    #mounts-status { padding: 0 2; height: 1; color: $text-muted; }
    #boot-info { height: auto; padding: 1 2; border: solid $warning; margin: 0 1; }
    #mounts-table-container { height: 1fr; margin: 0 1; border: solid $primary;
                              padding: 0 1; }
    #edit-row { height: 3; padding: 0 2; layout: horizontal; }
    #edit-row Input { width: 1fr; margin: 0 1; }
    #edit-row Button { margin: 0 1; }
    #command-log { height: 6; margin: 0 1; border: solid $primary-background;
                   padding: 0 1; }
    #action-buttons { height: 3; padding: 0 2; layout: horizontal; }
    #action-buttons Button { margin: 0 1; }
    """

    def __init__(self, **kw):
        super().__init__(**kw)
        self._entries: list[dict] = []
        self._selected_idx: int = -1

    @property
    def bridge(self):
        return getattr(self.app, "bridge", None)

    # ------------------------------------------------------------------
    # Compose
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Static("Montages des datasets", id="mounts-header")
        yield Static("Statut : chargement...", id="mounts-status")
        with Vertical(id="boot-info"):
            yield Label("Boot pool", classes="info-label")
            yield Label("boot_pool = ? mount = ?", id="boot-detail")
        with Vertical(id="mounts-table-container"):
            yield Label("Datasets et points de montage")
            yield DataTable(id="mounts-table")
        with Horizontal(id="edit-row"):
            yield Label("Mountpoint :")
            yield Input(placeholder="/mnt/...", id="edit-input")
            yield Button("Appliquer", variant="primary", id="btn-apply-edit")
        yield Log(id="command-log", highlight=True, auto_scroll=True)
        with Horizontal(id="action-buttons"):
            yield Button("Tout monter", variant="primary", id="btn-mount-all")
            yield Button("Verifier", variant="default", id="btn-verify")
            yield Button("Overlay", variant="warning", id="btn-overlay")
            yield Button("Teardown", variant="error", id="btn-teardown")
            yield Button(f"Valider {ARROW}", variant="success", id="btn-next")

    # ------------------------------------------------------------------
    # Textual lifecycle — AUCUN argument
    # ------------------------------------------------------------------

    def on_mount(self) -> None:
        """Textual lifecycle hook — pas de parametres."""
        dt = self.query_one("#mounts-table", DataTable)
        dt.add_columns("", "Dataset", "Role", "Montage actuel",
                        "Montage propose", "Monte", "Verifie")
        dt.cursor_type = "row"
        self._load_from_config()
        self._refresh_table()

    # ------------------------------------------------------------------
    # Config loading
    # ------------------------------------------------------------------

    def _load_from_config(self):
        self._entries.clear()
        cfg = getattr(self.app, "config", None)
        if not cfg:
            return
        rj = cfg.get("detection.report_json", "")
        if not rj:
            return
        try:
            report = json.loads(rj)
        except Exception:
            return

        existing = cfg.get("mounts", {})
        if not isinstance(existing, dict):
            existing = {}

        for ds in report.get("datasets", []):
            name = ds.get("name", "")
            role = ds.get("role", "unknown")
            mp = ds.get("mountpoint", "")
            is_m = mp not in ("", "-", "none")
            proposed = (existing.get(name, "")
                        or (mp if is_m else
                            MOUNT_PROPOSALS.get(role,
                                                f"/mnt/{name.split('/')[-1]}")))
            self._entries.append({
                "dataset": name, "role": role,
                "current": mp if is_m else "",
                "proposed": proposed,
                "mounted": is_m,
                "critical": role in ("boot", "efi"),
                "verified": False,
            })

    # ------------------------------------------------------------------
    # Table
    # ------------------------------------------------------------------

    def _refresh_table(self):
        dt = self.query_one("#mounts-table", DataTable)
        dt.clear()
        for e in self._entries:
            dt.add_row(
                "!" if e["critical"] else "",
                e["dataset"], e["role"],
                e["current"] or "-", e["proposed"],
                CHECK if e["mounted"] else "-",
                CHECK if e["verified"] else "-",
            )

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted):
        idx = event.cursor_row
        if idx is not None and 0 <= idx < len(self._entries):
            self._selected_idx = idx
            try:
                self.query_one("#edit-input", Input).value = (
                    self._entries[idx]["proposed"])
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Buttons
    # ------------------------------------------------------------------

    def on_button_pressed(self, e):
        bid = e.button.id or ""
        if bid == "btn-mount-all":
            self.action_mount_all()
        elif bid == "btn-verify":
            self.action_verify_all()
        elif bid == "btn-overlay":
            self.action_overlay_mount()
        elif bid == "btn-teardown":
            self.action_overlay_teardown()
        elif bid == "btn-next":
            self.action_next_step()
        elif bid == "btn-apply-edit":
            self._apply_edit()

    def _apply_edit(self):
        if self._selected_idx < 0 or self._selected_idx >= len(self._entries):
            return
        new_mp = self.query_one("#edit-input", Input).value.strip()
        if not new_mp:
            return
        self._entries[self._selected_idx]["proposed"] = new_mp
        self._refresh_table()

    # ------------------------------------------------------------------
    # Mount / Umount / Verify — actions
    # ------------------------------------------------------------------

    def action_mount_selected(self):
        if self._selected_idx < 0 or not self.bridge:
            return
        self._do_mount(self._entries[self._selected_idx])

    def action_umount_selected(self):
        if self._selected_idx < 0 or not self.bridge:
            return
        e = self._entries[self._selected_idx]
        ds = e["dataset"]
        self.bridge.emit(
            "mount.umount", dataset=ds, mountpoint=e.get("current", ""),
            callback=self._make_umount_callback(ds),
        )

    def action_mount_all(self):
        if not self.bridge:
            return
        for e in self._entries:
            if not e["mounted"] and e["proposed"]:
                self._do_mount(e)

    def action_verify_all(self):
        if not self.bridge:
            return
        for e in self._entries:
            if e["mounted"]:
                ds = e["dataset"]
                mp = e["current"] or e["proposed"]
                self.bridge.emit(
                    "mount.verify", dataset=ds, mountpoint=mp,
                    callback=self._make_verify_callback(ds),
                )

    def _do_mount(self, entry):
        ds = entry["dataset"]
        mp = entry["proposed"]
        self.bridge.emit(
            "mount.request", dataset=ds, mountpoint=mp,
            callback=self._make_mount_callback(ds),
        )
        self._log(f"  -> mount.request({ds} {ARROW} {mp})")

    # ------------------------------------------------------------------
    # Callback factories — chaque callback capture le dataset
    # via une methode factory au lieu d'une lambda pour eviter
    # les problemes de closure/scope
    # ------------------------------------------------------------------

    def _make_mount_callback(self, dataset: str):
        """Retourne un callback qui traite le resultat de montage."""
        def _cb(ticket):
            self._on_mount_done(ticket, dataset)
        return _cb

    def _make_umount_callback(self, dataset: str):
        def _cb(ticket):
            self._on_umount_done(ticket, dataset)
        return _cb

    def _make_verify_callback(self, dataset: str):
        def _cb(ticket):
            self._on_verify_done(ticket, dataset)
        return _cb

    # ------------------------------------------------------------------
    # Callbacks — noms _on_*_done pour eviter collision Textual
    # ------------------------------------------------------------------

    def _on_mount_done(self, ticket, dataset: str):
        """Callback montage termine — PAS le lifecycle Textual."""
        if ticket.status == "completed":
            for e in self._entries:
                if e["dataset"] == dataset:
                    e["mounted"] = True
                    e["current"] = e["proposed"]
                    break
            self._slog(f"  {CHECK} {dataset} monte")
        else:
            self._slog(f"  {CROSS} {dataset}: {ticket.error}")
        self._safe(self._refresh_table)

    def _on_umount_done(self, ticket, dataset: str):
        if ticket.status == "completed":
            for e in self._entries:
                if e["dataset"] == dataset:
                    e["mounted"] = False
                    e["current"] = ""
                    e["verified"] = False
                    break
            self._slog(f"  {CHECK} {dataset} demonte")
        else:
            self._slog(f"  {CROSS} {dataset}: {ticket.error}")
        self._safe(self._refresh_table)

    def _on_verify_done(self, ticket, dataset: str):
        if ticket.status == "completed":
            for e in self._entries:
                if e["dataset"] == dataset:
                    e["verified"] = True
                    break
        self._safe(self._refresh_table)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def action_refresh_mounts(self):
        self._load_from_config()
        self._refresh_table()

    def action_edit_mountpoint(self):
        try:
            self.query_one("#edit-input", Input).focus()
        except Exception:
            pass

    def action_next_step(self):
        cfg = getattr(self.app, "config", None)
        if cfg:
            for e in self._entries:
                if e["proposed"]:
                    cfg.set(f"mounts.{e['dataset']}", e["proposed"])
            try:
                cfg.save()
            except Exception:
                pass
        if hasattr(self.app, "navigate_next"):
            self.app.navigate_next()

    # ── Overlay ───────────────────────────────────────────────────────

    def action_overlay_mount(self) -> None:
        """Monte un squashfs + overlay pour le dataset selectionne."""
        if not self.bridge:
            return
        table = self.query_one("#mounts-table", DataTable)
        idx = table.cursor_row
        if idx is None or idx >= len(self._entries):
            self.notify("Selectionnez un dataset squashfs", severity="warning")
            return
        ds = self._entries[idx]
        dataset = ds.get("dataset", "")
        role = ds.get("role", "")
        mountpoint = ds.get("current", "")

        if role != "squashfs" and not dataset.endswith(".squashfs"):
            self.notify("Ce dataset n'est pas un squashfs", severity="warning")
            return

        # Determiner les chemins
        sfs_path = mountpoint if ds.get("mounted") else ""
        if not sfs_path:
            self.notify("Mountpoint squashfs requis (montez d'abord le dataset)", severity="warning")
            return

        merged = f"/mnt/overlay-{dataset.replace('/', '-')}"
        self._log(f"-> overlay.mount (sfs={sfs_path}, merged={merged})")
        self.bridge.emit(
            "overlay.mount",
            squashfs_path=sfs_path,
            merged=merged,
            callback=self._on_overlay_done,
        )

    def _on_overlay_done(self, ticket) -> None:
        if ticket.status == "failed":
            self._slog(f"{CROSS} Overlay echoue : {ticket.error}")
        else:
            result = ticket.result or {}
            merged = result.get("merged", "?")
            self._slog(f"{CHECK} Overlay monte : {merged}")
            self.action_refresh_mounts()

    def action_overlay_teardown(self) -> None:
        """Demonte l'overlay du dataset selectionne."""
        if not self.bridge:
            return
        table = self.query_one("#mounts-table", DataTable)
        idx = table.cursor_row
        if idx is None or idx >= len(self._entries):
            self.notify("Selectionnez un overlay a demonter", severity="warning")
            return
        ds = self._entries[idx]
        mountpoint = ds.get("current", "")

        if not mountpoint or mountpoint in ("-", "none"):
            self.notify("Pas de mountpoint a demonter", severity="warning")
            return

        self._log(f"-> overlay.teardown (merged={mountpoint})")
        self.bridge.emit(
            "overlay.teardown",
            merged=mountpoint,
            cleanup_dirs=True,
            callback=self._on_teardown_done,
        )

    def _on_teardown_done(self, ticket) -> None:
        if ticket.status == "failed":
            self._slog(f"{CROSS} Teardown echoue : {ticket.error}")
        else:
            self._slog(f"{CHECK} Overlay demonte")
            self.action_refresh_mounts()

    def update_from_snapshot(self, s):
        pass

    # ------------------------------------------------------------------
    # Logging thread-safe
    # ------------------------------------------------------------------

    def _log(self, m):
        try:
            self.query_one("#command-log", Log).write_line(m)
        except Exception:
            pass

    def _slog(self, m):
        try:
            self.app.call_from_thread(self._log, m)
        except Exception:
            self._log(m)

    def _safe(self, fn):
        try:
            self.app.call_from_thread(fn)
        except Exception:
            fn()
