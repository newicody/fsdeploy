# PLAN.md — fsdeploy (branche `dev`)

> **Dernière mise à jour** : 2026-04-18
> **Itération worker** : 83
> **Codebase** : ~23 550 lignes Python, 62 intents, 23 écrans
> **Tâche active** : **20.1** — voir `add.md`

---

## ✅ Terminé

| ID | Description |
|----|-------------|
| — | Daemon, Scheduler Event→Intent→Task, Bridge tickets, Config 19 sections, Logging structlog, Bus sources, RuntimeState, IntentLog Huffman, Metrics, TaskGraph DAG |
| — | 62 intents @register_intent (pool, detection, mount, kernel, initramfs, presets, coherence, snapshots, stream, zbm, init, config, module, boot, health, security, scheduler, debug, log, integration) |
| — | 34 task implementations réelles (80+ lignes) |
| — | 10 écrans câblés bridge : detection, mounts, initramfs, kernel, presets, coherence, snapshots, stream, zbm, module_registry |
| — | launch.sh complet, multi-init, tests bridge, docs |
| 8.1a+b | Scheduler↔bridge unifié |
| 10.1 | Unicode detection.py |
| 10.3 | LoggedDummyBridge |
| 10.4 | welcome.py lazy imports |
| 10.5a | 3 doublons supprimés (graph_enhanced, security_enhanced, navigation) |
| 10.5b | Refs test nettoyées, 5 orphelins supprimés (multiarch_screen, livegraph, partition_detection, fsdeploy/ui/), fix history.py Textual 8.x |
| 9.1 | live/setup.py linux-headers dynamique (déjà implémenté : `_install_packages()` détecte via `uname -r`) |
| 16.20-54 | Intents mount/pool + doublons + cli.py |
| 17.7 | pyproject.toml |
| Phase 1-6 | Stabilisation TUI, robustesse, init/, tests, nettoyage |
| 7.0 | launch.sh branche dev |

---

## 🚧 Tâche active — 20.1

Voir `add.md`.

---

## ⏳ Restant

### P0

Aucune tâche bloquante restante.

### P1 — Fonctionnalité

| ID | Description |
|----|-------------|
| **20.1** | Supprimer 6 scripts racine orphelins + résoudre double nesting fsdeploy/fsdeploy/ |
| **19.1** | Implémenter 2 vrais task stubs : `snapshot/destroy.py` (class pass), `dataset/create.py` (class pass). Les 14 autres sont des re-exports valides (7) ou modules désactivés volontairement (7). |
| **19.2** | Câbler 13 écrans au bridge : config, config_snapshot, crosscompile, debug, error_log, graph, history, intentlog, metrics, monitoring, multiarch, security, welcome |
| **11.1** | SquashFS mount/overlay |
| **11.2** | Switch rootfs à chaud (task rootfs/switch.py 178L existe, UI non câblée) |

### P2 — Qualité

| ID | Description |
|----|-------------|
| **20.3** | Fusionner docs bridge doublons (bridge-ui-scheduler.md vs bridge_ui_scheduler.md) |
| **20.4** | Supprimer tests/contrib/ (duplique fsdeploy/contrib/) |
| **17.1** | SecurityResolver complet |
| **18.1-3** | Tests unitaires, intégration, TUI Pilot |
| **7.3** | Refresh docs |

---

## Stats

| Métrique | Valeur |
|----------|--------|
| Fichiers Python | ~90 |
| Lignes Python | ~23 550 |
| Intents enregistrés | 62 |
| Écrans TUI | 23 (propres, 0 orphelin) |
| Écrans câblés bridge | 10 |
| Écrans non câblés | 13 |
| Tasks réelles (80+ L) | 34 |
| Tasks stubs réels | 2 |
