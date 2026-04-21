# PLAN.md — fsdeploy

> **Itération** : 135 | **Status** : Migration complète (23/23 écrans)
> **Tâche active** : **18.2** — Tests overlay + intent pipeline

---

## ✅ Terminé
- Correction de `bridge.py` et `app.py`.
- Injection du bridge dans tous les 23 écrans (commit c0d7262 + migrations suivantes).
- **Tâche 24.1.b COMPLÈTE** : Tous les écrans utilisent `self.bridge.emit()` et ont `SchedulerBridge.default()` dans `on_mount()`.

## 🚧 Tâche active — 18.2
- **Tests overlay + intent pipeline**
- Validation du bon fonctionnement du bridge avec les événements réels.
- Vérification que les intents sont correctement convertis en tâches.

---

## ⏳ Restant
| ID | Prio | Description |
|----|------|-------------|
| **18.2** | P1 | Tests overlay + intent pipeline |
| **24.2** | P2 | Documentation et exemples d'utilisation du bridge |
