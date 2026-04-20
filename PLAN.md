# PLAN.md — fsdeploy (branche `dev`)

> **Dernière mise à jour** : 2026-04-20
> **Itération worker** : 105
> **Codebase** : ~24 273 lignes Python
> **Tâche active** : **24.1** — Refonte Bridge & Patch Global Screens

---

## ✅ Terminé

| ID | Description |
|----|-------------|
| 23.3 | Mount namespace pour DatasetProbeTask (anti-leak) |
| 22.3 | Fix __init__.py (38L, sys.path lib/ restauré, CLI fonctionnelle) |
| 22.1-2 | Fix __main__.py (parent + lib/ dans sys.path) |
| 18.1 | Tests SecurityResolver + Isolation (19 tests) |
| 11.1-2 | SquashFS/overlay (overlay.py, overlay_intent.py, mounts.py) |
| 23.1-2 | Isolation (isolation.py MountIsolation + CgroupLimits, executor intégré) |
| 19.2 | 23 écrans câblés — 0 violation |
| 17.1 | SecurityResolver 4 niveaux + executor |
| 20.1-3, 21.1, 10.5, 9.1, 8.1, 16.x, 17.7, 7.0, Phase 1-6 | Tout le reste |

---

## 🚧 Tâche active — 24.1
Refonte de la communication UI/Scheduler :
- Correction du constructeur et des signatures de `bridge.py`.
- Migration exhaustive des 23 écrans vers le standard `bridge.emit()`.
Voir `add.md`.

---

## ⏳ Restant

| ID | Prio | Description |
|----|------|-------------|
| **18.2** | P1 | Tests overlay + intent pipeline |
| **18.3** | P2 | Tests TUI Pilot |

---

## Bilan

| Métrique | Valeur |
|----------|--------|
| Lignes Python | ~24 273 |
| Intents | 71 |
| Écrans | 23 (tous câblés) |
| Tasks réelles | 34 |
| Tests | 15 fichiers |
| Violations architecture | 0 (écrans), 8 (cli.py — acceptable pour CLI) |