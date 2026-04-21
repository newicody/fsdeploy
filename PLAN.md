# PLAN.md — fsdeploy

> **Dernière mise à jour** : 2026-04-21
> **Note** : Repository synchronisé (Push OK).
> **Tâche active** : **24.1** — Refonte Bridge & Migration Screens (lib/ui/)

---

## ✅ Terminé
| ID | Description |
|----|-------------|
| 23.3 | Mount namespace pour DatasetProbeTask (ZFS isolation) |

---

## 🚧 Tâche active — 24.1
**Réparation Structurelle UI (Code Réel) :**
- Correction de `fsdeploy/lib/ui/bridge.py` (init + emit + uuid).
- Correction de `fsdeploy/lib/ui/app.py` (instanciation).
- Migration des 23 écrans dans `fsdeploy/lib/ui/screens/`.
- **Statut** : Prêt pour injection automatique.

---

## ⏳ Restant
| ID | Prio | Description |
|----|------|-------------|
| **18.2** | P1 | Tests overlay + intent pipeline |