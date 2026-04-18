# PLAN.md — fsdeploy (branche `dev`)

> **Dernière mise à jour** : 2026-04-18
> **Itération worker** : 82
> **Codebase** : ~24 450 lignes Python, 62 intents enregistrés
> **Tâche active** : **10.5b** — Nettoyage écrans orphelins + fix Textual 8.x

---

## ✅ Terminé

### Infrastructure core
| Composant | Détails |
|-----------|---------|
| Daemon | `daemon.py` — processus racine, orchestre tout |
| Scheduler | Event → Intent → Task pipeline complet (EventQueue, IntentQueue, TaskGraph, ThreadPool) |
| Bridge | `lib/ui/bridge.py` + `lib/scheduler/bridge.py` — tickets, thread-safe, poll() |
| Config | `config.py` — configobj 19 sections, configspec, recherche multi-chemins |
| Logging | `log.py` — structlog + ASCII fallback TERM=linux |
| Security | `scheduler/security/` — decorator, resolver (base) |
| Bus sources | TimerSource, InotifySource, UdevSource, SocketSource (base) |
| Runtime | `RuntimeState` thread-safe avec Lock |
| IntentLog | Huffman codec + persistent log |
| Metrics | `scheduler/metrics.py` |
| TaskGraph | DAG + resource graph |

### 62 Intents enregistrés (@register_intent)
| Domaine | Intents |
|---------|---------|
| **pool** | `pool.import`, `pool.import_all`, `pool.status` |
| **detection** | `detection.start`, `detection.partitions`, `detection.probe_datasets` |
| **mount** | `mount.request`, `mount.umount`, `mount.verify` |
| **kernel** | `kernel.list`, `kernel.compile`, `kernel.install`, `kernel.provision`, `kernel.switch`, `kernel.unprovision`, `kernel.registry.scan`, `kernel.mainline.detect`, `kernel.module.detect`, `kernel.module.integrate` |
| **initramfs** | `initramfs.build`, `initramfs.list` |
| **presets** | `preset.save`, `preset.delete`, `preset.list`, `preset.activate` |
| **coherence** | `coherence.check`, `coherence.quick`, `coherence.verify` |
| **snapshots** | `snapshot.create`, `snapshot.list`, `snapshot.rollback` |
| **stream** | `stream.start`, `stream.stop`, `stream.status` |
| **zbm** | `zbm.install`, `zbm.status`, `zbm.validate`, `zfsbootmenu.integrate` |
| **init** | 11 intents (detect, install, configure, boot.check, boot.config, config.detect, service.control, integration.install, postinstall.check, upstart_sysv.install/test) |
| **config** | `config.snapshot.save`, `config.snapshot.restore`, `config.snapshot.list` |
| **module** | `module.install`, `module.list`, `module.uninstall`, `module.update` |
| **other** | `boot.init.generate`, `health.check`, `security.status`, `scheduler.verify`, `debug.exec`, `log.export`, `log.stats`, `integration.test` |

### 34 Task implementations réelles (80+ lignes)
`coherence/check.py` (1282L), `zbm/validate.py` (725L), `init_install.py` (618L), `detect/role_patterns.py` (485L), `kernel/provision.py` (346L), `kernel/registry.py` (303L), `kernel/switch.py` (273L), `boot/init.py` (213L), `live/setup.py` (208L), `detect/environment.py` (204L), `boot/initramfs.py` (180L), `rootfs/switch.py` (178L), `stream/youtube.py` (163L), `snapshot/create.py` (140L), `dataset/mount.py` (150L), `pool/status.py` (110L), + 18 autres

### 12 écrans câblés au bridge
`detection`, `mounts`, `initramfs`, `kernel`, `presets`, `coherence`, `snapshots`, `stream`, `zbm`, `module_registry`, `multiarch_screen`*, `partition_detection`*

### Tâches PLAN/worker terminées
| ID | Description |
|----|-------------|
| 8.1a+b | Scheduler↔bridge unifié |
| 10.1 | Unicode detection.py |
| 10.3 | LoggedDummyBridge |
| 10.4 | welcome.py lazy imports |
| 10.5a | 3 doublons supprimés (graph_enhanced, security_enhanced, navigation) — **refs test pas nettoyées** |
| 16.20-54 | Intents mount/pool + doublons intents + cli.py |
| 17.7 | pyproject.toml |
| Phase 1-6 | Stabilisation TUI, robustesse, init/, tests, nettoyage |
| 7.0 | launch.sh branche dev |

---

## 🚧 Tâche active — 10.5b

Voir `add.md`.

---

## ⏳ Restant — Par priorité

### P0 — Bloquant / crash

| ID | Description |
|----|-------------|
| **10.5b** | Nettoyer refs test cassées + supprimer 4 orphelins + fix Textual 8.x history.py |
| **9.1** | `live/setup.py` linux-headers dynamique (hardcodé `linux-headers-amd64`) |

### P1 — Fonctionnalité manquante

| ID | Description |
|----|-------------|
| **19.1** | Implémenter 16 task stubs (<20 lignes) : `kernel/compile`, `kernel/install`, `pool/export`, 7× `module/*`, `dataset/create`, `dataset/destroy`, `rootfs/mount`, `rootfs/update`, `snapshot/rollback`, `snapshot/destroy` |
| **19.2** | Câbler 8 écrans info au bridge : `config`, `config_snapshot`, `debug`, `history`, `security`, `monitoring`, `metrics`, `intentlog` |
| **19.3** | Câbler 4 écrans avancés : `graph` (données live), `crosscompile`, `multiarch`, `error_log` |
| **11.1** | SquashFS mount/overlay setup |
| **11.2** | Switch rootfs à chaud (task existe, UI non câblée) |

### P2 — Qualité / nettoyage

| ID | Description |
|----|-------------|
| **20.1** | Supprimer scripts racine orphelins : `check_imports_7.8.py`, `cleanup_contrib.sh`, `cleanup_lib_ui.sh`, `remove_tests_fsdeploy.py`, `test_all.py`, `test_integration_7_17.py` |
| **20.2** | Résoudre double nesting `fsdeploy/fsdeploy/` |
| **20.3** | Fusionner docs bridge doublons (`bridge-ui-scheduler.md` vs `bridge_ui_scheduler.md`) |
| **20.4** | Supprimer `tests/contrib/` (duplique `fsdeploy/contrib/`) |
| **17.1** | SecurityResolver complet |
| **18.1-3** | Tests unitaires, intégration, TUI Pilot |
| **7.3** | Refresh docs |

---

## Stats

| Métrique | Valeur |
|----------|--------|
| Fichiers Python | ~95 |
| Lignes Python | ~24 450 |
| Intents enregistrés | 62 |
| Écrans TUI | 22+ (dont 3 orphelins à supprimer) |
| Écrans câblés bridge | 12 |
| Tasks réelles (80+ L) | 34 |
| Tasks stubs (< 20 L) | 16 |