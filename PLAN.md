# PLAN.md — fsdeploy (branche `dev`)

> **Dernière mise à jour** : 2026-04-21
> **Itération worker** : 106
> **Tâche active** : **24.1** — Refonte Bridge/Bus & Patch Global Screens

---

## ✅ Terminé
| ID | Description |
|----|-------------|
| 23.3 | Mount namespace pour DatasetProbeTask (anti-leak) |
| 23.1-2 | Isolation & CgroupLimits (executor intégré) |
| 19.2 | Structure initiale des 23 écrans câblés |

---

## 🚧 Tâche active — 24.1
**Réparation de la communication UI/Scheduler :**
- Fix du constructeur `bridge.py` (acceptation de runtime/store).
- Implémentation de la méthode `emit()` avec IDs `uuid`.
- Correction du bug de signature `ticket_id` dans `_log_ticket`.
- Migration systématique des 23 écrans vers le nouveau standard.

---

## ⏳ Restant
| ID | Prio | Description |
|----|------|-------------|
| **18.2** | P1 | Tests overlay + intent pipeline |
| **18.3** | P2 | Tests TUI Pilot |