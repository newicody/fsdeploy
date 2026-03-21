"""
fsdeploy.ui.screens.detection
===============================
Ecran de detection — 100% bus events.

ZERO import de lib/. ZERO subprocess. Toutes les operations :

  bridge.emit("pool.status")                    → pools detectes
  bridge.emit("dataset.list", pool="boot_pool") → datasets listes
  bridge.emit("detection.probe_datasets", datasets=[...]) → roles detectes
  bridge.emit("detection.partitions")           → partitions detectees
  bridge.emit("pool.import", pool="fast_pool")  → import pool

Les resultats arrivent via les callbacks enregistres sur chaque emit.
Le scheduler gere : locks, security, logging, HuffmanStore.
"""

import json
import os
import time
from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, Container
from textual.screen import Screen
from textual.widgets import (
    Button, DataTable, Label, Log, ProgressBar, Rule, Static,
)


IS_FB = os.environ.get("TERM") == "linux"
CHECK = "[OK]" if IS_FB else "✅"
CROSS = "[!!]" if IS_FB else "❌"
WARN  = "[??]" if IS_FB else "⚠️"
ARROW = "->" if IS_FB else "→"


class DetectionScreen(Screen):

    BINDINGS = [
        Binding("r", "run_detection", "Scanner", show=True),
        Binding("v", "validate", "Valider", show=True),
        Binding("enter", "next_step", "Suivant", show=True),
        Binding("escape", "app.pop_screen", "Retour", show=False),
    ]

    DEFAULT_CSS = """
    DetectionScreen { layout: vertical; }
    #detection-header { height: auto; padding: 1 2; text-style: bold; }
    #detection-status { padding: 0 2; height: 1; color: $text-muted; }
    #progress-bar { height: 1; margin: 0 2; }
    #tables-container { height: 1fr; layout: vertical; }
    #pools-section { height: auto; max-height: 30%; margin: 0 1;
                     border: solid $primary; padding: 0 1; }
    #datasets-section { height: 1fr; margin: 0 1;
                        border: solid $primary; padding: 0 1; }
    #partitions-section { height: auto; max-height: 20%; margin: 0 1;
                          border: solid $accent; padding: 0 1; }
    .table-title { text-style: bold; height: 1; }
    #command-log { height: 8; margin: 0 1; border: solid $primary-background;
                   padding: 0 1; }
    #action-buttons { height: 3; padding: 0 2; layout: horizontal; }
    #action-buttons Button { margin: 0 1; }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = "detection"
        self._scanning = False

        # Etat accumule
        self._pools: list[dict] = []
        self._datasets: list[dict] = []
        self._probes: dict[str, dict] = {}   # dataset_name → {role, confidence, ...}
        self._partitions: list[dict] = []

        # Tickets en cours pour le suivi multi-phases
        self._list_tickets: list[str] = []
        self._list_done_count: int = 0
        self._list_expected: int = 0

    @property
    def bridge(self):
        return getattr(self.app, "bridge", None)

    # ── Compose ─────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Static("Detection du systeme", id="detection-header")
        yield Static("Statut : en attente", id="detection-status")
        yield ProgressBar(total=100, show_eta=False, id="progress-bar")

        with Container(id="tables-container"):
            with Vertical(id="pools-section"):
                yield Label("Pools ZFS", classes="table-title")
                yield DataTable(id="pools-table")
            with Vertical(id="datasets-section"):
                yield Label("Datasets", classes="table-title")
                yield DataTable(id="datasets-table")
            with Vertical(id="partitions-section"):
                yield Label("Partitions", classes="table-title")
                yield DataTable(id="partitions-table")

        yield Log(id="command-log", highlight=True, auto_scroll=True)

        with Horizontal(id="action-buttons"):
            yield Button("Scanner", variant="primary", id="btn-scan")
            yield Button(f"Valider {ARROW}", variant="success",
                         id="btn-validate", disabled=True)
            yield Button("Importer un pool", variant="warning",
                         id="btn-import")

    def on_mount(self) -> None:
        pt = self.query_one("#pools-table", DataTable)
        pt.add_columns("Pool", "Etat", "Taille", "Utilise", "Libre")
        pt.cursor_type = "row"

        dt = self.query_one("#datasets-table", DataTable)
        dt.add_columns("Dataset", "Role", "Confiance", "Utilise",
                        "Dispo", "Details")
        dt.cursor_type = "row"

        pp = self.query_one("#partitions-table", DataTable)
        pp.add_columns("Device", "Type", "Label", "UUID", "Taille", "Role")
        pp.cursor_type = "row"

        self.action_run_detection()

    # ── Buttons ─────────────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "btn-scan":
            self.action_run_detection()
        elif bid == "btn-validate":
            self.action_validate()
        elif bid == "btn-import":
            self._import_pools()

    # ═══════════════════════════════════════════════════════════════
    # PHASE 1 : pools + partitions
    # ═══════════════════════════════════════════════════════════════

    def action_run_detection(self) -> None:
        """Lance la detection — tout via le bus."""
        if self._scanning or not self.bridge:
            if not self.bridge:
                self._log(f"{CROSS} Bridge non disponible")
            return

        self._scanning = True
        self._pools.clear()
        self._datasets.clear()
        self._probes.clear()
        self._partitions.clear()
        self._list_tickets.clear()
        self._list_done_count = 0
        self._list_expected = 0

        self._set_status("Phase 1 : detection des pools...")
        self._progress(5)
        self.query_one("#btn-scan", Button).disabled = True
        self.query_one("#btn-validate", Button).disabled = True
        self._log("=== Detection lancee via le bus ===")

        # Emettre les events phase 1
        self.bridge.emit("pool.status",
                         callback=self._on_pools_done)
        self._log("  -> pool.status")

        self.bridge.emit("detection.partitions",
                         callback=self._on_partitions_done)
        self._log("  -> detection.partitions")

    def _on_pools_done(self, ticket) -> None:
        """Callback : pools detectes."""
        if ticket.status == "failed":
            self._safe_log(f"{CROSS} Erreur pools : {ticket.error}")
            self._finish_scan()
            return

        result = ticket.result
        self._parse_pools(result)
        self._safe_log(f"  {CHECK} {len(self._pools)} pools detectes")
        self._safe_progress(25)

        # Phase 2 : lister les datasets
        self._launch_dataset_listing()

    def _parse_pools(self, result: Any) -> None:
        """Parse le resultat de PoolStatusTask."""
        if isinstance(result, dict):
            output = result.get("output", "")
            current = ""
            for line in output.splitlines():
                s = line.strip()
                if s.startswith("pool:"):
                    current = s.split(":", 1)[1].strip()
                    self._pools.append({
                        "name": current, "state": "ONLINE",
                        "size": "-", "alloc": "-", "free": "-",
                        "imported": True,
                    })
                elif s.startswith("state:") and current:
                    state = s.split(":", 1)[1].strip()
                    for p in self._pools:
                        if p["name"] == current:
                            p["state"] = state
        elif isinstance(result, list):
            self._pools = result

    def _on_partitions_done(self, ticket) -> None:
        """Callback : partitions detectees."""
        if ticket.status == "completed" and isinstance(ticket.result, list):
            self._partitions = ticket.result
            self._safe_log(f"  {CHECK} {len(self._partitions)} partitions")

    # ═══════════════════════════════════════════════════════════════
    # PHASE 2 : lister les datasets par pool
    # ═══════════════════════════════════════════════════════════════

    def _launch_dataset_listing(self) -> None:
        """Emet dataset.list pour chaque pool importe."""
        if not self.bridge:
            return

        self._set_status("Phase 2 : listing des datasets...")
        imported = [p["name"] for p in self._pools if p.get("imported", True)]

        if not imported:
            self._safe_log(f"{WARN} Aucun pool importe")
            self._launch_probes()
            return

        self._list_expected = len(imported)
        self._list_done_count = 0

        for pool in imported:
            tid = self.bridge.emit("dataset.list", pool=pool,
                                   callback=self._on_dataset_list_done)
            self._list_tickets.append(tid)
            self._safe_log(f"  -> dataset.list({pool})")

    def _on_dataset_list_done(self, ticket) -> None:
        """Callback : datasets d'un pool."""
        if ticket.status == "completed" and isinstance(ticket.result, list):
            for ds in ticket.result:
                self._datasets.append(ds)
            self._safe_log(f"  +{len(ticket.result)} datasets")

        self._list_done_count += 1

        if self._list_done_count >= self._list_expected:
            self._safe_log(f"  Total : {len(self._datasets)} datasets")
            self._safe_progress(50)
            self._launch_probes()

    # ═══════════════════════════════════════════════════════════════
    # PHASE 3 : inspecter le contenu de chaque dataset
    # ═══════════════════════════════════════════════════════════════

    def _launch_probes(self) -> None:
        """Emet detection.probe_datasets avec la liste complete."""
        if not self.bridge or not self._datasets:
            self._safe_log(f"{WARN} Aucun dataset a inspecter")
            self._safe_call(self._finish_scan)
            return

        self._set_status("Phase 3 : inspection du contenu...")

        ds_list = []
        for ds in self._datasets:
            ds_list.append({
                "name": ds.get("name", ""),
                "mountpoint": ds.get("mountpoint", ""),
                "mounted": ds.get("mounted", "") == "yes",
            })

        self.bridge.emit("detection.probe_datasets",
                         datasets=ds_list,
                         callback=self._on_probes_done)
        self._safe_log(f"  -> detection.probe_datasets ({len(ds_list)} datasets)")

    def _on_probes_done(self, ticket) -> None:
        """Callback : probes terminees."""
        if ticket.status == "completed":
            # Le resultat peut etre un dict par dataset ou une liste
            result = ticket.result
            if isinstance(result, dict) and "dataset" in result:
                self._probes[result["dataset"]] = result
            elif isinstance(result, list):
                for r in result:
                    if isinstance(r, dict) and "dataset" in r:
                        self._probes[r["dataset"]] = r

        # Aussi chercher les probes individuelles dans le state
        self._collect_probes_from_state()

        self._safe_progress(90)
        self._safe_log(f"  {CHECK} {len(self._probes)} datasets inspectes")
        self._safe_call(self._finish_scan)

    def _collect_probes_from_state(self) -> None:
        """
        Recupere les resultats des DatasetProbeTask individuelles
        depuis runtime.state.completed.
        """
        runtime = getattr(self.app, "runtime", None)
        if not runtime:
            return

        state = runtime.state
        with state._lock:
            for task_id, entry in state.completed.items():
                result = entry.get("result", {})
                if isinstance(result, dict) and "dataset" in result:
                    ds_name = result["dataset"]
                    if ds_name not in self._probes:
                        self._probes[ds_name] = result

    # ═══════════════════════════════════════════════════════════════
    # FIN DU SCAN
    # ═══════════════════════════════════════════════════════════════

    def _finish_scan(self) -> None:
        """Met a jour l'affichage apres le scan complet."""
        self._scanning = False
        self._progress(100)
        self._refresh_tables()
        self.query_one("#btn-scan", Button).disabled = False

        n_unknown = sum(1 for ds in self._datasets
                        if self._probes.get(ds.get("name", ""), {})
                            .get("role", "unknown") == "unknown")
        status = "complete" if self._pools and n_unknown == 0 else "partial"
        icon = CHECK if status == "complete" else WARN
        self._set_status(f"{icon} {status} — {len(self._pools)} pools, "
                         f"{len(self._datasets)} datasets, "
                         f"{len(self._partitions)} partitions")
        self.query_one("#btn-validate", Button).disabled = (not self._pools)
        self._log("=== Detection terminee ===")

    # ═══════════════════════════════════════════════════════════════
    # IMPORT POOLS
    # ═══════════════════════════════════════════════════════════════

    def _import_pools(self) -> None:
        """Importe les pools non importes via le bus."""
        if not self.bridge:
            return

        exported = [p["name"] for p in self._pools
                    if not p.get("imported", True)]
        if not exported:
            self.notify("Tous les pools sont importes.", timeout=3)
            return

        for pool_name in exported:
            self.bridge.emit(
                "pool.import", pool=pool_name,
                callback=lambda t, n=pool_name: self._on_pool_imported(t, n),
            )
            self._log(f"  -> pool.import({pool_name})")

    def _on_pool_imported(self, ticket, pool_name: str) -> None:
        if ticket.status == "completed":
            self._safe_log(f"{CHECK} {pool_name} importe")
            self._safe_call(self.action_run_detection)
        else:
            self._safe_log(f"{CROSS} Import {pool_name} : {ticket.error}")

    # ═══════════════════════════════════════════════════════════════
    # VALIDATE + NEXT
    # ═══════════════════════════════════════════════════════════════

    def action_validate(self) -> None:
        if not self._pools:
            self.notify("Aucune detection.", severity="warning")
            return
        self._save_to_config()
        self.notify(f"{CHECK} Detection validee.", timeout=3)

    def action_next_step(self) -> None:
        if not self._pools:
            self.notify("Lancez un scan d'abord.", severity="warning")
            return
        self._save_to_config()
        if hasattr(self.app, "navigate_next"):
            self.app.navigate_next()

    # ── Tables ──────────────────────────────────────────────────────

    def _refresh_tables(self) -> None:
        pt = self.query_one("#pools-table", DataTable)
        pt.clear()
        for p in self._pools:
            state = p.get("state", "?")
            icon = CHECK if state == "ONLINE" else (
                WARN if state == "DEGRADED" else CROSS)
            pt.add_row(p["name"], f"{icon} {state}",
                       p.get("size", "-"), p.get("alloc", "-"),
                       p.get("free", "-"))

        dt = self.query_one("#datasets-table", DataTable)
        dt.clear()
        for ds in self._datasets:
            name = ds.get("name", "?")
            probe = self._probes.get(name, {})
            role = probe.get("role", "?")
            conf = probe.get("confidence", 0)
            conf_str = f"{conf:.0%}" if conf > 0 else "-"
            details = probe.get("details", "")[:40] or "-"
            dt.add_row(name, role, conf_str,
                       ds.get("used", "-"), ds.get("avail", "-"), details)

        pp = self.query_one("#partitions-table", DataTable)
        pp.clear()
        for p in self._partitions:
            uid = p.get("uuid", "-")
            if len(uid) > 12:
                uid = uid[:12] + "..."
            pp.add_row(p.get("device", "?"), p.get("fstype", "-"),
                       p.get("label", "-"), uid,
                       p.get("size", "-"), p.get("role", "-"))

    # ── Refresh depuis le store ─────────────────────────────────────

    def update_from_snapshot(self, snapshot: dict) -> None:
        """Affiche les events recents du scheduler pendant le scan."""
        if not self._scanning:
            return
        for evt in snapshot.get("recent_events", []):
            name = evt.get("name", "")
            if any(k in name for k in ("detect", "probe", "pool", "dataset")):
                self._log(f"  [bus] {name}")

    # ── Config ──────────────────────────────────────────────────────

    def _save_to_config(self) -> None:
        app = self.app
        cfg = getattr(app, "config", None)
        if not cfg:
            return

        imported = [p["name"] for p in self._pools if p.get("imported", True)]
        for i, key in enumerate(["boot_pool", "fast_pool", "data_pool"]):
            if i < len(imported):
                cfg.set(f"pool.{key}", imported[i])

        for ds in self._datasets:
            name = ds.get("name", "")
            probe = self._probes.get(name, {})
            if probe.get("role") == "boot":
                mp = ds.get("mountpoint", "")
                if mp and mp not in ("-", "none"):
                    cfg.set("pool.boot_mount", mp)
                break

        for p in self._partitions:
            if p.get("role") == "efi":
                cfg.set("partition.efi_device", p.get("device", ""))
                break

        report = {
            "pools": self._pools,
            "datasets": [{**ds, **self._probes.get(ds.get("name", ""), {})}
                         for ds in self._datasets],
            "partitions": self._partitions,
        }
        cfg.set("detection.report_json", json.dumps(report))
        cfg.set("detection.status", "complete" if self._pools else "none")
        cfg.set("detection.detected_at", time.strftime("%Y-%m-%d %H:%M:%S"))

        try:
            cfg.save()
        except Exception:
            pass

    # ── UI helpers (thread-safe) ────────────────────────────────────

    def _log(self, msg: str) -> None:
        try:
            self.query_one("#command-log", Log).write_line(msg)
        except Exception:
            pass

    def _safe_log(self, msg: str) -> None:
        """Log depuis un callback (potentiellement hors thread Textual)."""
        try:
            self.app.call_from_thread(self._log, msg)
        except Exception:
            self._log(msg)

    def _set_status(self, text: str) -> None:
        try:
            self.query_one("#detection-status", Static).update(
                f"Statut : {text}")
        except Exception:
            pass

    def _progress(self, val: int) -> None:
        try:
            self.query_one("#progress-bar", ProgressBar).update(progress=val)
        except Exception:
            pass

    def _safe_progress(self, val: int) -> None:
        try:
            self.app.call_from_thread(self._progress, val)
        except Exception:
            self._progress(val)

    def _safe_call(self, fn) -> None:
        """Appelle fn dans le thread Textual."""
        try:
            self.app.call_from_thread(fn)
        except Exception:
            fn()
