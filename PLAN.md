# PLAN.md — fsdeploy (branche `dev`)

> **Dernière mise à jour** : 2026-04-19
> **Itération worker** : 87
> **Codebase** : ~24 099 lignes Python, 71 intents, 23 écrans
> **Tâche active** : **11.2** — voir `add.md`

---

## ✅ Terminé

| ID | Description |
|----|-------------|
| — | Daemon, Scheduler, Bridge, Config, Logging, Bus, Runtime, IntentLog, Metrics, TaskGraph |
| — | 71 intents, 33+ tasks réelles, launch.sh, multi-init |
| 11.1 | SquashFS mount + overlay setup (overlay.py 195L, overlay_intent.py 59L, 5 intents) |
| 23.1-2 | Isolation : isolation.py + cgroups intégrés executor |
| 22.1, 19.2, 17.1, 20.1-3, 21.1, 10.5, 9.1, 8.1, 16.x, 17.7, 7.0, Phase 1-6 | Tout le reste |

---

## 🚧 Tâche active — 11.2

Voir `add.md`.

---

## ⏳ Restant

### P1

| ID | Description |
|----|-------------|
| **11.2** | Ajouter overlay mount/teardown dans l'écran mounts |
| **23.3** | Mount namespace pour DatasetProbeTask |

### P2

| ID | Description |
|----|-------------|
| **18.1** | Tests smoke (imports + instantiation) |
| **18.2** | Tests unitaires core (resolver, executor, bridge) |
| **18.3** | Tests intégration scheduler |