"""
fsdeploy.ui.screens.mounts
============================
Ecran de montages — 100% bus events.

ZERO import de lib/. Toutes les operations :

  bridge.emit("mount.request", dataset="...", mountpoint="/mnt/boot")
  bridge.emit("mount.umount", dataset="...", mountpoint="/mnt/boot")
  bridge.emit("mount.verify", dataset="...", mountpoint="/mnt/boot")

Les resultats de la detection sont lus depuis la config
(detection.report_json) — pas d'import de DetectionReport.
"""

import json
import os
from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import (
    Button, DataTable, Input, Label, Log, Rule, Static,
)


IS_FB = os.environ.get("TERM") == "linux"
CHECK = "[OK]" if IS_FB else "✅"
CROSS = "[!!]" if IS_FB else "❌"
WARN  = "[??]" if IS_FB else "⚠️"
ARROW = "->" if IS_FB else "→"

# Propositions de montage par role (aucun import de lib/)
MOUNT_PROPOSALS = {
    "boot": "/mnt/boot",
    "efi": "/mnt/boot/efi",
    "rootfs": "/mnt/rootfs",
    "kernel": "/mnt/boot",
    "modules": "/mnt/boot/modules",
    "initramfs": "/mnt/boot",
    "squashfs": "/mnt/boot/images",
    "overlay": "/mnt/overlay",
    "python_env": "/mnt/boot/python",
}


class MountsScreen(Screen):

    BINDINGS = [
        Binding("r", "refresh_mounts", "Rafraichir", show=True),
        Binding("m", "mount_selected", "Monter", show=True),
        Binding("u", "umount_selected", "Demonter", show=True),
        Binding("e", "edit_mountpoint", "Modifier", show=True),
        Binding("a", "mount_all", "Tout monter", show=True),
        Binding("v", "verify_all", "Verifier", show=True),
        Binding("enter", "next_step", "Suivant", show=True),
        Binding("escape", "app.pop_screen", "Retour", show=False),
    ]

    DEFAULT_CSS = """
    MountsScreen { layout: vertical; }
    #mounts-header { height: auto; padding: 1 2; text-style: bold; }
    #mounts-status { padding: 0 2; height: 1; color: $text-muted; }
    #boot-info { height: auto; padding: 1 2; border: solid $warning;
                 margin: 0 1; }
    #boot-info .info-label { text-style: bold; }
    #mounts-table-container { height: 1fr; margin: 0 1;
                              border: solid $primary; padding: 0 1; }
    #edit-row { height: 3; padding: 0 2; layout: horizontal; }
    #edit-row Input { width: 1fr; margin: 0 1; }
    #edit-row Button { margin: 0 1; }
    #command-log { height: 6; margin: 0 1; border: solid $primary-background;
                   padding: 0 1; }
    #action-buttons { height: 3; padding: 0 2; layout: horizontal; }
    #action-buttons Button { margin: 0 1; }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = "mounts"
        self._entries: list[dict] = []  # {dataset, role, current, proposed, mounted, verified}
        self._selected_idx: int = -1
        self._pending_mounts: dict[str, str] = {}  # ticket_id → dataset

    @property
    def bridge(self):
        return getattr(self.app, "bridge", None)

    # ── Compose ─────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Static("Montages des datasets", id="mounts-header")
        yield Static("Statut : chargement...", id="mounts-status")

        with Vertical(id="boot-info"):
            yield Label("Boot pool", classes="info-label")
            yield Label("boot_pool = ?   mount = ?", id="boot-detail")

        with Vertical(id="mounts-table-container"):
            yield Label("Datasets et points de montage", classes="info-label")
            yield DataTable(id="mounts-table")

        with Horizontal(id="edit-row"):
            yield Label("Mountpoint :")
            yield Input(placeholder="/mnt/...", id="edit-input")
            yield Button("Appliquer", variant="primary", id="btn-apply-edit")

        yield Log(id="command-log", highlight=True, auto_scroll=True)

        with Horizontal(id="action-buttons"):
            yield Button("Tout monter", variant="primary", id="btn-mount-all")
            yield Button("Verifier", variant="default", id="btn-verify")
            yield Button(f"Valider {ARROW}", variant="success", id="btn-next")

    def on_mount(self) -> None:
        dt = self.query_one("#mounts-table", DataTable)
        dt.add_columns("", "Dataset", "Role", "Montage actuel",
                        "Montage propose", "Monte", "Verifie")
        dt.cursor_type = "row"
        self._load_from_config()
        self._refresh_table()

    # ── Chargement depuis la config ─────────────────────────────────

    def _load_from_config(self) -> None:
        """Charge les resultats de detection depuis fsdeploy.conf."""
        self._entries.clear()
        cfg = getattr(self.app, "config", None)
        if not cfg:
            self._set_status(f"{WARN} Config non disponible")
            return

        report_json = cfg.get("detection.report_json", "")
        if not report_json:
            self._set_status(f"{WARN} Aucune detection. Lancez la detection d'abord.")
            return

        try:
            report = json.loads(report_json)
        except json.JSONDecodeError:
            self._set_status(f"{CROSS} Rapport de detection invalide")
            return

        # Montages existants dans [mounts]
        existing_mounts = cfg.get("mounts", {})
        if not isinstance(existing_mounts, dict):
            existing_mounts = {}

        for ds in report.get("datasets", []):
            name = ds.get("name", "")
            role = ds.get("role", "unknown")
            mp = ds.get("mountpoint", "")
            is_mounted = mp not in ("", "-", "none")

            # Montage propose : config > detection > proposition par role
            proposed = existing_mounts.get(name, "")
            if not proposed:
                proposed = mp if is_mounted else MOUNT_PROPOSALS.get(
                    role, f"/mnt/{name.split('/')[-1]}")

            self._entries.append({
                "dataset": name,
                "role": role,
                "current": mp if is_mounted else "",
                "proposed": proposed,
                "mounted": is_mounted,
                "critical": role in ("boot", "efi"),
                "verified": False,
            })

        self._update_boot_info()
        self._set_status(f"{CHECK} {len(self._entries)} datasets charges")

    def _update_boot_info(self) -> None:
        boot = next((e for e in self._entries if e["role"] == "boot"), None)
        if boot:
            text = (f"boot_pool = {boot['dataset']}   "
                    f"mount = {boot['proposed']}   "
                    f"{'(monte)' if boot['mounted'] else '(non monte)'}")
        else:
            text = f"{WARN} Aucun dataset boot detecte"
        try:
            self.query_one("#boot-detail", Label).update(text)
        except Exception:
            pass

    # ── Table ───────────────────────────────────────────────────────

    def _refresh_table(self) -> None:
        dt = self.query_one("#mounts-table", DataTable)
        dt.clear()
        for e in self._entries:
            critical = "!" if e["critical"] else ""
            mounted = CHECK if e["mounted"] else "-"
            verified = CHECK if e["verified"] else "-"
            dt.add_row(critical, e["dataset"], e["role"],
                       e["current"] or "-", e["proposed"],
                       mounted, verified)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        idx = event.cursor_row
        if 0 <= idx < len(self._entries):
            self._selected_idx = idx
            self.query_one("#edit-input", Input).value = \
                self._entries[idx]["proposed"]

    # ── Buttons ─────────────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "btn-mount-all":
            self.action_mount_all()
        elif bid == "btn-verify":
            self.action_verify_all()
        elif bid == "btn-next":
            self.action_next_step()
        elif bid == "btn-apply-edit":
            self._apply_edit()

    def _apply_edit(self) -> None:
        if self._selected_idx < 0 or self._selected_idx >= len(self._entries):
            self.notify("Selectionnez un dataset.", severity="warning")
            return
        new_mp = self.query_one("#edit-input", Input).value.strip()
        if not new_mp:
            return
        self._entries[self._selected_idx]["proposed"] = new_mp
        self._refresh_table()
        ds = self._entries[self._selected_idx]["dataset"]
        self.notify(f"Mountpoint modifie : {ds}", timeout=2)

    # ═══════════════════════════════════════════════════════════════
    # MOUNT / UMOUNT — via le bus
    # ═══════════════════════════════════════════════════════════════

    def action_mount_selected(self) -> None:
        """Monte le dataset selectionne via le bus."""
        if self._selected_idx < 0 or not self.bridge:
            return
        entry = self._entries[self._selected_idx]
        self._mount_one(entry)

    def action_umount_selected(self) -> None:
        """Demonte le dataset selectionne via le bus."""
        if self._selected_idx < 0 or not self.bridge:
            return
        entry = self._entries[self._selected_idx]
        self._umount_one(entry)

    def action_mount_all(self) -> None:
        """Monte tous les datasets non montes via le bus."""
        if not self.bridge:
            return
        count = 0
        for entry in self._entries:
            if not entry["mounted"] and entry["proposed"]:
                self._mount_one(entry)
                count += 1
        self._log(f"  {count} montages demandes via le bus")

    def _mount_one(self, entry: dict) -> None:
        """Emet un event de montage pour un dataset."""
        ds = entry["dataset"]
        mp = entry["proposed"]
        if not mp:
            return

        tid = self.bridge.emit(
            "mount.request",
            dataset=ds,
            mountpoint=mp,
            callback=lambda t, e=entry: self._on_mount_done(t, e),
        )
        self._pending_mounts[tid] = ds
        self._log(f"  -> mount.request({ds} {ARROW} {mp})")

    def _on_mount_done(self, ticket, entry: dict) -> None:
        """Callback : montage termine."""
        ds = entry["dataset"]
        if ticket.status == "completed":
            entry["mounted"] = True
            entry["current"] = entry["proposed"]
            self._safe_log(f"{CHECK} {ds} monte")
        else:
            self._safe_log(f"{CROSS} {ds} : {ticket.error}")

        self._pending_mounts.pop(ticket.id, None)

        # Si plus de montages pending, refresh
        if not self._pending_mounts:
            self._safe_call(self._after_mount_all)

    def _after_mount_all(self) -> None:
        """Appele quand tous les montages sont termines."""
        self._refresh_table()
        self._update_boot_info()
        mounted = sum(1 for e in self._entries if e["mounted"])
        self._set_status(f"{CHECK} {mounted}/{len(self._entries)} montes")

    def _umount_one(self, entry: dict) -> None:
        """Emet un event de demontage."""
        if not self.bridge:
            return
        ds = entry["dataset"]
        mp = entry["current"] or entry["proposed"]

        self.bridge.emit(
            "mount.umount",
            dataset=ds,
            mountpoint=mp,
            callback=lambda t, e=entry: self._on_umount_done(t, e),
        )
        self._log(f"  -> mount.umount({ds})")

    def _on_umount_done(self, ticket, entry: dict) -> None:
        if ticket.status == "completed":
            entry["mounted"] = False
            entry["current"] = ""
            entry["verified"] = False
            self._safe_log(f"  Demonte {entry['dataset']}")
        else:
            self._safe_log(f"{CROSS} Demontage {entry['dataset']} : {ticket.error}")
        self._safe_call(self._refresh_table)

    # ═══════════════════════════════════════════════════════════════
    # VERIFY — via le bus
    # ═══════════════════════════════════════════════════════════════

    def action_verify_all(self) -> None:
        """Verifie tous les montages via le bus."""
        if not self.bridge:
            return

        for entry in self._entries:
            if entry["mounted"] and entry["proposed"]:
                self.bridge.emit(
                    "mount.verify",
                    dataset=entry["dataset"],
                    mountpoint=entry["proposed"],
                    callback=lambda t, e=entry: self._on_verify_done(t, e),
                )

    def _on_verify_done(self, ticket, entry: dict) -> None:
        if ticket.status == "completed":
            result = ticket.result
            if isinstance(result, dict):
                entry["verified"] = result.get("verified", False)
            else:
                entry["verified"] = bool(result)
        else:
            entry["verified"] = False
        self._safe_call(self._refresh_table)

    # ═══════════════════════════════════════════════════════════════
    # REFRESH / NAVIGATE
    # ═══════════════════════════════════════════════════════════════

    def action_refresh_mounts(self) -> None:
        """Recharge depuis la config."""
        self._load_from_config()
        self._refresh_table()
        self.notify("Montages rafraichis.", timeout=2)

    def action_edit_mountpoint(self) -> None:
        self.query_one("#edit-input", Input).focus()

    def action_next_step(self) -> None:
        self._save_to_config()
        if hasattr(self.app, "navigate_next"):
            self.app.navigate_next()

    # ── Config ──────────────────────────────────────────────────────

    def _save_to_config(self) -> None:
        cfg = getattr(self.app, "config", None)
        if not cfg:
            return

        for entry in self._entries:
            if entry["proposed"]:
                cfg.set(f"mounts.{entry['dataset']}", entry["proposed"])

        boot = next((e for e in self._entries if e["role"] == "boot"), None)
        if boot and boot["proposed"]:
            cfg.set("pool.boot_mount", boot["proposed"])

        try:
            cfg.save()
            self.notify(f"{CHECK} Montages sauvegardes.", timeout=2)
        except Exception as e:
            self.notify(f"{CROSS} Erreur : {e}", severity="error")

    # ── UI helpers (thread-safe) ────────────────────────────────────

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
            self.query_one("#mounts-status", Static).update(
                f"Statut : {text}")
        except Exception:
            pass

    def _safe_call(self, fn) -> None:
        try:
            self.app.call_from_thread(fn)
        except Exception:
            fn()
