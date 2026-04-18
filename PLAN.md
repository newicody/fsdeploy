# PLAN.md — fsdeploy (branche `dev`)

> **Dernière mise à jour** : 2026-04-18
> **Itération worker** : 87
> **Codebase** : ~23 485 lignes Python, 62 intents, 23 écrans (tous câblés)
> **Tâche active** : **22.1** — voir `add.md`

---

## ✅ Terminé

| ID | Description |
|----|-------------|
| — | Daemon, Scheduler, Bridge, Config, Logging, Bus, Runtime, IntentLog, Metrics, TaskGraph |
| — | 62 intents, 34 task implementations, launch.sh, multi-init |
| 19.2 | Tous les 23 écrans câblés — 0 violation architecture |
| 20.1-3 | Nettoyage complet (orphelins, double nesting, docs, tests/contrib) |
| 17.1 | SecurityResolver avec niveaux allow/deny/require_sudo/dry_run_only + intégré executor |
| 21.1, 10.5a+b, 9.1, 8.1, 16.x, 17.7, 7.0, Phase 1-6 | Tout le reste |

---

## 🚧 Tâche active — 22.1

Voir `add.md`.

---

## ⏳ Restant

### P0

| ID | Description |
|----|-------------|
| **22.1** | Fix `__main__.py` — CLI cassé (régression 20.1 : `fsdeploy/fsdeploy/` supprimé mais import pas mis à jour) |

### P1

| ID | Description |
|----|-------------|
| **11.1** | SquashFS mount/overlay tasks |
| **11.2** | Switch rootfs à chaud |

### P2

| ID | Description |
|----|-------------|
| **18.1-3** | Tests |