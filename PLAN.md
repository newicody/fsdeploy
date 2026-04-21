# PLAN.md — fsdeploy

> **Itération** : 107 | **Status** : 12/23 écrans initiés.
> **Tâche active** : **24.1.b** — Finalisation du Patch Global (Lot 2 + Migration Emit)

---

## ✅ Terminé
- Correction de `bridge.py` et `app.py`.
- Injection du bridge dans 12 écrans (kernel, presets, coherence, mounts, zbm, config_snapshot, graph, crosscompile, stream, security, snapshots, monitoring).

## 🚧 Tâche active — 24.1.b
- **Couverture totale** : Appliquer le patch aux ~11 écrans restants dans `fsdeploy/lib/ui/screens/`.
- **Migration fonctionnelle** : Remplacer systématiquement `self.app.bus.emit` par `self.bridge.emit` dans les 23 fichiers.
- **Validation** : Vérifier que chaque écran possède bien l'init `self.bridge` dans `on_mount`.

---

## ⏳ Restant
| ID | Prio | Description |
|----|------|-------------|
| **18.2** | P1 | Tests overlay + intent pipeline |