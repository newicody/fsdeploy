# PLAN.md — fsdeploy (branche `dev`)

> **Dernière mise à jour** : 2026-04-18
> **Itération worker** : 87
> **Codebase** : ~23 220 lignes Python, 62 intents, 23 écrans, 11 câblés
> **Tâche active** : **19.2b** — voir `add.md`

---

## ✅ Terminé

| ID | Description |
|----|-------------|
| — | Daemon, Scheduler, Bridge, Config, Logging, Bus, Runtime, IntentLog, Metrics, TaskGraph |
| — | 62 intents, 34 task implementations, launch.sh, multi-init, tests, docs |
| 19.2a | SecurityScreen câblé au bridge (security.status) |
| 21.1 | overlay_check.py créé, SnapshotDestroyTask implémenté, DatasetCreateTask re-exporté |
| 20.1 | Scripts racine orphelins + double nesting supprimés |
| 10.5a+b | Doublons/orphelins UI, fix Textual 8.x |
| 9.1, 8.1, 16.20-54, 17.7, 7.0, Phase 1-6 | Tout le reste |

---

## 🚧 Tâche active — 19.2b

Voir `add.md`.

---

## ⏳ Restant

### P1

| ID | Description |
|----|-------------|
| **19.2b** | Câbler GraphScreen au bridge (scheduler state live) |
| **19.2c** | Câbler metrics, monitoring, intentlog, history, error_log |
| **19.2d** | Câbler config_snapshot, crosscompile, multiarch |
| **11.1** | SquashFS mount/overlay |
| **11.2** | Switch rootfs à chaud |

### P2

| ID | Description |
|----|-------------|
| **20.3** | Fusionner docs bridge doublons |
| **20.4** | Supprimer tests/contrib/ |
| **17.1** | SecurityResolver complet |
| **18.1-3** | Tests |

---

## Écrans câblés : 11/23

| Câblés | Non câblés |
|--------|-----------|
| detection, mounts, initramfs, kernel, presets, coherence, snapshots, stream, zbm, module_registry, security | config*, config_snapshot, crosscompile, debug*, error_log, graph, history, intentlog, metrics, monitoring, multiarch, welcome* |

*\* config/debug/welcome n'ont pas besoin de bridge (accès config direct ou pas de données dynamiques)*