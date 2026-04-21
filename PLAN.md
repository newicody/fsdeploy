# PLAN.md — fsdeploy

> **Status** : 12/23 initialisés, 0/23 migrés fonctionnellement.
> **Stratégie** : Approche par lots (Batches) pour éviter la saturation.

---

## 🚧 Tâche active — 24.1 (FINITION)
**Objectif : Migration fonctionnelle totale vers `bridge.emit`.**

1. **Vérification (Shell)** : Identifier les fichiers qui contiennent encore `bus.emit`.
2. **Batch 1 (11 restants)** : Initialiser le Bridge dans `on_mount`.
3. **Batch 2 (Les 23)** : Remplacer `self.app.bus.emit` par `self.bridge.emit`.

---

## ✅ Historique Récent
- `bridge.py` et `app.py` sont 100% OK.
- Premier lot de 12 écrans initialisés (structure uniquement).