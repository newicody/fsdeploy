# PLAN.md — fsdeploy

> **Dernière mise à jour** : 2026-04-21
> **Tâche active** : **24.1** — Refonte Bridge (PATH FIX)

---

## 🚧 Tâche active — 24.1
**Réparation de la communication UI (Chemins définitifs) :**
- Le code source RÉEL est dans `fsdeploy/lib/ui/`.
- Ignorer tout dossier `fsdeploy/ui/` à la racine (doublon potentiel).
- Mise à jour de `bridge.py`, `app.py` et des 23 écrans dans `lib/ui/`.