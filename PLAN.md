# PLAN.md — fsdeploy (branche `dev`)

> **Dernière mise à jour** : 2026-04-18
> **Itération worker** : 87
> **Codebase** : ~23 485 lignes Python, 62 intents, 23 écrans (tous câblés)
> **Tâche active** : **20.3** — voir `add.md`

---

## ✅ Terminé

| ID | Description |
|----|-------------|
| — | Daemon, Scheduler, Bridge, Config, Logging, Bus, Runtime, IntentLog, Metrics, TaskGraph |
| — | 62 intents, 34 task implementations, launch.sh, multi-init |
| **19.2** | **Tous les 23 écrans câblés — 0 violation architecture** |
| | bridge.emit: coherence, config_snapshot, crosscompile, detection, initramfs, kernel, module_registry, mounts, multiarch, presets, security, snapshots, stream, zbm |
| | get_scheduler_state: graph, metrics, monitoring |
| | app.store: error_log, history, intentlog |
| | app.config/subprocess: config, debug, welcome |
| 21.1 | overlay_check.py, SnapshotDestroyTask, DatasetCreateTask |
| 20.1 | Scripts racine orphelins + double nesting supprimés |
| 10.5a+b, 9.1, 8.1, 16.x, 17.7, 7.0, Phase 1-6 | Tout le reste |

---

## 🚧 Tâche active — 20.3

Voir `add.md`.

---

## ⏳ Restant

### P1

| ID | Description |
|----|-------------|
| **20.3** | Fusionner docs bridge doublons + supprimer tests/contrib/ |
| **17.1** | SecurityResolver — ajouter niveaux allow/deny/require_sudo/dry_run_only explicites |
| **11.1** | SquashFS mount/overlay tasks |
| **11.2** | Switch rootfs à chaud |

### P2

| ID | Description |
|----|-------------|
| **18.1-3** | Tests unitaires, intégration, TUI Pilot |