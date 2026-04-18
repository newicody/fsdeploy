# PLAN.md — fsdeploy (branche `dev`)

> **Dernière mise à jour** : 2026-04-18
> **Itération worker** : 87
> **Codebase** : ~23 160 lignes Python, 62 intents, 23 écrans
> **Tâche active** : **19.2a** — voir `add.md`

---

## ✅ Terminé

| ID | Description |
|----|-------------|
| — | Daemon, Scheduler, Bridge, Config, Logging, Bus, Runtime, IntentLog, Metrics, TaskGraph |
| — | 62 intents, 34 task implementations, 10 écrans câblés bridge |
| 21.1 | Fix debug.py import cassé, SnapshotDestroyTask implémenté, DatasetCreateTask re-exporté |
| 20.1 | Scripts racine orphelins + double nesting supprimés |
| 10.5a+b | Doublons/orphelins UI, fix Textual 8.x |
| 9.1 | live/setup.py linux-headers dynamique |
| 8.1, 16.20-54, 17.7, 7.0, Phase 1-6 | Infrastructure, intents, config, launch.sh |

---

## 🚧 Tâche active — 19.2a

Voir `add.md`.

---

## ⏳ Restant

### P1

| ID | Description |
|----|-------------|
| **19.2a** | Câbler `security.py` au bridge (template pour les autres écrans) |
| **19.2b** | Câbler `graph.py` au bridge (scheduler state live) |
| **19.2c** | Câbler `metrics.py`, `monitoring.py`, `intentlog.py`, `history.py`, `error_log.py` |
| **19.2d** | Câbler `config_snapshot.py`, `crosscompile.py`, `multiarch.py` |
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

## Écrans — État câblage bridge

| Écran | Bridge | Notes |
|-------|--------|-------|
| detection | ✅ | pool.import_all → pool.status → probe |
| mounts | ✅ | mount.request |
| initramfs | ✅ | initramfs.build |
| kernel | ✅ | kernel.list, kernel.switch |
| presets | ✅ | preset.save/list/activate |
| coherence | ✅ | coherence.check |
| snapshots | ✅ | snapshot.create/list |
| stream | ✅ | stream.start/stop |
| zbm | ✅ | zbm.validate/install |
| module_registry | ✅ | module.list |
| security | ❌ → **19.2a** | bridge property existe, intent security.status prêt |
| graph | ❌ | bridge property existe, stub 61L |
| config | — | Utilise self.app.config directement (normal) |
| welcome | — | Pas de données dynamiques |
| debug | — | Appels subprocess directs (acceptable pour debug) |
| config_snapshot | ❌ | Import direct lib/ (violation) |
| history | ❌ | Import direct intentlog |
| intentlog | ❌ | — |
| metrics | ❌ | — |
| monitoring | ❌ | — |
| error_log | ❌ | — |
| crosscompile | ❌ | — |
| multiarch | ❌ | — |