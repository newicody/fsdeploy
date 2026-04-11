# add.md — Action 2.3 : Notifications TUI unifiées

**Date** : 2026-04-11

---

## Problème

`app.py` appelle `bridge.poll()` dans `_refresh_from_store()` mais ignore la valeur de retour (liste de tickets terminés). Les tâches qui échouent passent inaperçues — aucun toast affiché.

---

## Correction

Dans `fsdeploy/lib/ui/app.py`, modifier `_refresh_from_store()` :

```python
def _refresh_from_store(self) -> None:
    if self.bridge:
        try:
            just_done = self.bridge.poll()
            for ticket in just_done:
                if ticket.status == "failed":
                    self.notify(
                        f"Echec: {ticket.event_name} — {ticket.error}",
                        severity="error", timeout=5,
                    )
                elif ticket.status == "completed":
                    self.notify(
                        f"OK: {ticket.event_name}",
                        severity="information", timeout=3,
                    )
        except Exception:
            pass
    # ... reste inchangé (store snapshot)
```

---

## Fichier Aider

```
fsdeploy/lib/ui/app.py
```

---

## Après

Phase 2 terminée. Prochaine : **Phase 3** (3.0 Export/import configuration).
