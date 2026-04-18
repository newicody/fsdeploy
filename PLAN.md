# PLAN.md — fsdeploy (branche `dev`)

> **Dernière mise à jour** : 2026-04-19
> **Itération worker** : 87
> **Codebase** : ~23 794 lignes Python, 67 intents, 23 écrans
> **Tâche active** : **23.2** — voir `add.md`

---

## ✅ Terminé

| ID | Description |
|----|-------------|
| — | Daemon, Scheduler, Bridge, Config, Logging, Bus, Runtime, IntentLog, Metrics, TaskGraph |
| — | 67 intents, 33 tasks réelles, launch.sh, multi-init |
| 23.1 | `isolation.py` créé — MountIsolation + CgroupLimits (285L) |
| 22.1 | Fix __main__.py |
| 19.2 | 23 écrans câblés — 0 violation |
| 17.1 | SecurityResolver 4 niveaux + intégration executor |
| 20.1-3, 21.1, 10.5, 9.1, 8.1, 16.x, 17.7, 7.0, Phase 1-6 | Tout le reste |

---

## 🚧 Tâche active — 23.2

Voir `add.md`.

---

## Phase 23 : Isolation — Progression

| ID | Description | État |
|----|-------------|------|
| 23.1 | Créer `isolation.py` (MountIsolation + CgroupLimits) | ✅ |
| **23.2** | Intégrer cgroups dans executor + decorator DSL | En cours |
| 23.3 | Mount namespace pour DatasetProbeTask (multiprocessing + os.unshare) | À faire |
| 23.4 | Options isolation dans security decorator | À faire |

---

## ⏳ Restant

### P1

| ID | Description |
|----|-------------|
| **23.2** | Cgroups dans executor |
| **23.3** | Mount namespace pour probe |
| **11.1** | SquashFS mount/overlay tasks |
| **11.2** | Switch rootfs à chaud |

### P2

| ID | Description |
|----|-------------|
| **18.1-3** | Tests |