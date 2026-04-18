# PLAN.md — fsdeploy (branche `dev`)

> **Dernière mise à jour** : 2026-04-18
> **Itération worker** : 87
> **Codebase** : ~23 360 lignes Python, 62 intents, 23 écrans
> **Tâche active** : **19.2f** — voir `add.md`

---

## ✅ Terminé

| ID | Description |
|----|-------------|
| — | Daemon, Scheduler, Bridge, Config, Logging, Bus, Runtime, IntentLog, Metrics, TaskGraph |
| — | 62 intents, 34 task implementations, launch.sh, multi-init, tests, docs |
| 19.2a-e | Tous les écrans câblés ou nettoyés : **0 violation architecture** |
| 21.1 | overlay_check.py, SnapshotDestroyTask, DatasetCreateTask |
| 20.1 | Scripts racine orphelins + double nesting supprimés |
| 10.5a+b, 9.1, 8.1, 16.x, 17.7, 7.0, Phase 1-6 | Tout le reste |

---

## Écrans — État final : 0 violation

| Méthode | Écrans (18 câblés) |
|---------|-------------------|
| bridge.emit | coherence, config_snapshot, detection, initramfs, kernel, module_registry, mounts, presets, security, snapshots, stream, zbm |
| get_scheduler_state | graph, metrics, monitoring |
| app.store | error_log, history, intentlog |
| **Stubs données fictives** | **crosscompile, multiarch** |
| Pas besoin de bridge | config, debug, welcome |

---

## 🚧 Tâche active — 19.2f

Voir `add.md`.

---

## ⏳ Restant

### P1

| ID | Description |
|----|-------------|
| **19.2f** | Câbler crosscompile + multiarch (derniers stubs à données fictives) |
| **11.1** | SquashFS mount/overlay tasks |
| **11.2** | Switch rootfs à chaud (task existe 178L, écran non câblé) |
| **17.1** | SecurityResolver complet (allow/deny/require_sudo/dry_run_only) |

### P2

| ID | Description |
|----|-------------|
| **20.3** | Fusionner docs bridge doublons |
| **18.1-3** | Tests unitaires, intégration, TUI Pilot |