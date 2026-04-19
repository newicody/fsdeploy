# PLAN.md — fsdeploy (branche `dev`)

> **Dernière mise à jour** : 2026-04-19
> **Itération worker** : 87
> **Codebase** : ~24 182 lignes Python, 71 intents, 23 écrans, 34 tasks
> **Tâche active** : **18.1** — voir `add.md`

---

## ✅ Terminé

| ID | Description |
|----|-------------|
| 11.1-2 | SquashFS/overlay tasks + intents + UI mounts (overlay.py, overlay_intent.py, mounts.py) |
| 23.1-2 | Isolation : isolation.py (MountIsolation + CgroupLimits) + executor intégré |
| 22.1 | Fix __main__.py |
| 19.2 | 23 écrans câblés — 0 violation |
| 17.1 | SecurityResolver 4 niveaux + executor |
| 20.1-3, 21.1, 10.5, 9.1, 8.1, 16.x, 17.7, 7.0, Phase 1-6 | Tout le reste |

---

## 🚧 Tâche active — 18.1

Voir `add.md`.

---

## ⏳ Restant

### P1

| ID | Description |
|----|-------------|
| **18.1** | Tests : security resolver + executor + isolation |
| **18.2** | Tests : overlay tasks + intent pipeline |
| **23.3** | Mount namespace pour DatasetProbeTask |

### P2

| ID | Description |
|----|-------------|
| **18.3** | Tests TUI Pilot |

---

## Bilan projet

| Métrique | Valeur |
|----------|--------|
| Lignes Python | ~24 182 |
| Intents | 71 |
| Écrans TUI | 23 (tous câblés) |
| Tasks réelles (80+L) | 34 |
| Violations architecture | 0 |
| Tests existants | 13 fichiers / ~1 593 lignes |
| Couverture SecurityResolver | ❌ aucun test |
| Couverture Isolation | ❌ aucun test |
| Couverture Overlay | ❌ aucun test |