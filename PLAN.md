# PLAN.md — fsdeploy (branche `dev`)

> **Dernière mise à jour** : 2026-04-18
> **Itération worker** : 87
> **Codebase** : ~23 330 lignes Python, 62 intents, 23 écrans
> **Tâche active** : **19.2d** — voir `add.md`

---

## ✅ Terminé

| ID | Description |
|----|-------------|
| — | Daemon, Scheduler, Bridge, Config, Logging, Bus, Runtime, IntentLog, Metrics, TaskGraph |
| — | 62 intents, 34 task implementations, launch.sh, multi-init, tests, docs |
| 19.2a | SecurityScreen câblé |
| 19.2b | GraphScreen câblé (get_scheduler_state, timer 1s) |
| 19.2c | ConfigSnapshotScreen réécrit (bridge.emit list/save/restore) |
| 19.2e | history.py + error_log.py réécrits (app.store au lieu d'import direct intent_log) |
| — | intentlog.py déjà propre (app.store, pas d'import direct) |
| 21.1, 20.1, 10.5a+b, 9.1, 8.1, 16.x, 17.7, 7.0, Phase 1-6 | Tout le reste |

---

## 🚧 Tâche active — 19.2d

Voir `add.md`.

---

## ⏳ Restant

### P1

| ID | Description |
|----|-------------|
| **19.2d** | Câbler monitoring.py (seule violation restante : `from ...scheduler.metrics`) |
| **19.2f** | Câbler crosscompile + multiarch (stubs avec données fictives, pas de violation) |
| **11.1** | SquashFS mount/overlay |
| **11.2** | Switch rootfs à chaud |

### P2

| ID | Description |
|----|-------------|
| **20.3** | Fusionner docs bridge doublons |
| **17.1** | SecurityResolver complet |
| **18.1-3** | Tests |

---

## Violations architecture restantes

| Fichier | Violation |
|---------|-----------|
| `monitoring.py:12` | `from ...scheduler.metrics import get_task_metrics, get_performance_stats` |

C'est la **seule** violation restante dans les écrans.

---

## Écrans : état final

| Statut | Écrans |
|--------|--------|
| Câblés bridge.emit | coherence, config_snapshot, detection, initramfs, kernel, module_registry, mounts, presets, security, snapshots, stream, zbm |
| Câblés get_scheduler_state | graph, metrics |
| Câblés app.store | error_log, history, intentlog |
| Violation import | **monitoring** |
| Stubs données fictives | crosscompile, multiarch |
| Pas besoin de bridge | config, debug, welcome |