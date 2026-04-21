# PLAN.md — fsdeploy

> **Itération** : 107 | **Status** : Migration partielle (12/23 écrans)
> **Tâche active** : **24.1.b** — Finalisation et Migration Fonctionnelle

---

## ✅ Terminé
- Correction de `bridge.py` et `app.py`.
- Injection du bridge dans le premier lot d'écrans (commit c0d7262).

## 🚧 Tâche active — 24.1.b
- **Couverture totale** : Patcher les 11 écrans restants dans `fsdeploy/lib/ui/screens/`.
- **Remplacement critique** : Migrer tous les `self.app.bus.emit` vers `self.bridge.emit` dans les 23 fichiers.
- **Validation** : Vérifier que `SchedulerBridge.default()` est bien utilisé partout.

---

## ⏳ Restant
| ID | Prio | Description |
|----|------|-------------|
| **18.2** | P1 | Tests overlay + intent pipeline |
