# add.md — 11.2 : Ajouter overlay mount/teardown dans MountsScreen

## Fichier : `fsdeploy/lib/ui/screens/mounts.py`

Les intents `overlay.mount` et `overlay.teardown` existent (11.1). Il faut les rendre accessibles depuis l'écran mounts.

## Modifications (ne PAS réécrire tout le fichier — ajouter aux emplacements indiqués)

### 1. Ajouter 2 bindings dans BINDINGS (après la ligne `verify_all`)

```python
        Binding("o", "overlay_mount", "Overlay", show=True),
        Binding("t", "overlay_teardown", "Teardown", show=True),
```

### 2. Ajouter 2 boutons dans le bloc `action-buttons` (après `btn-verify`)

```python
            yield Button("Overlay", variant="warning", id="btn-overlay")
            yield Button("Teardown", variant="error", id="btn-teardown")
```

### 3. Ajouter le handler bouton dans `on_button_pressed` (ou le créer si absent)

```python
    @on(Button.Pressed, "#btn-overlay")
    def handle_overlay(self) -> None:
        self.action_overlay_mount()

    @on(Button.Pressed, "#btn-teardown")
    def handle_teardown(self) -> None:
        self.action_overlay_teardown()
```

Si `on_button_pressed` existe déjà avec des if/elif, ajouter les cas :
```python
        elif bid == "btn-overlay":
            self.action_overlay_mount()
        elif bid == "btn-teardown":
            self.action_overlay_teardown()
```

### 4. Ajouter les 2 méthodes action + callbacks (à la fin du fichier, avant `update_from_snapshot`)

```python
    # ── Overlay ───────────────────────────────────────────────────────

    def action_overlay_mount(self) -> None:
        """Monte un squashfs + overlay pour le dataset selectionne."""
        if not self.bridge:
            return
        table = self.query_one("#mounts-table", DataTable)
        idx = table.cursor_row
        if idx is None or idx >= len(self._datasets):
            self.notify("Selectionnez un dataset squashfs", severity="warning")
            return
        ds = self._datasets[idx]
        dataset = ds.get("name", "")
        role = ds.get("role", "")
        mountpoint = ds.get("mountpoint", "")

        if role != "squashfs" and not dataset.endswith(".squashfs"):
            self.notify("Ce dataset n'est pas un squashfs", severity="warning")
            return

        # Determiner les chemins
        sfs_path = mountpoint if mountpoint not in ("-", "none", "") else ""
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
            self._safe_log(f"{CROSS} Overlay echoue : {ticket.error}")
        else:
            result = ticket.result or {}
            merged = result.get("merged", "?")
            self._safe_log(f"{CHECK} Overlay monte : {merged}")
            self.action_refresh_mounts()

    def action_overlay_teardown(self) -> None:
        """Demonte l'overlay du dataset selectionne."""
        if not self.bridge:
            return
        table = self.query_one("#mounts-table", DataTable)
        idx = table.cursor_row
        if idx is None or idx >= len(self._datasets):
            self.notify("Selectionnez un overlay a demonter", severity="warning")
            return
        ds = self._datasets[idx]
        mountpoint = ds.get("mountpoint", "")

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
            self._safe_log(f"{CROSS} Teardown echoue : {ticket.error}")
        else:
            self._safe_log(f"{CHECK} Overlay demonte")
            self.action_refresh_mounts()
```

## Critères

1. `grep "overlay_mount\|overlay_teardown" fsdeploy/lib/ui/screens/mounts.py` → bindings et actions présents
2. `grep "overlay.mount\|overlay.teardown" fsdeploy/lib/ui/screens/mounts.py` → bridge.emit présents
3. `grep "btn-overlay\|btn-teardown" fsdeploy/lib/ui/screens/mounts.py` → boutons présents
4. Aucun import depuis lib/ ajouté (tout passe par bridge.emit)
