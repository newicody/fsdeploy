# PLAN.md — fsdeploy

> **Itération** : 108 | **Objectif** : Connexion fonctionnelle totale.
> **Stratégie** : Migration par lots (Batches) pour éviter la saturation mémoire.

---

## 🚧 Tâche active — 24.1 (FINITION)
1. **Recensement** : Identifier via `grep` les fichiers restants.
2. **Patch Lot A (11 fichiers)** : Injection de `SchedulerBridge` dans `on_mount`.
3. **Migration Lot B (23 fichiers)** : Remplacement global de `bus.emit` par `bridge.emit`.

---

## ✅ Historique
- Refonte de `bridge.py` validée.
- Instanciation dans `app.py` validée.