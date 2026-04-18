# PLAN.md — fsdeploy (branche `dev`)

> **Dernière mise à jour** : 2026-04-18
> **Itération worker** : 82
> **Tâche active** : **10.5** — Supprimer doublons écrans (voir `add.md`)

---

## ✅ Terminé

| ID | Description | Notes |
|----|-------------|-------|
| — | Architecture daemon/scheduler/bridge | Event → Intent → Task pipeline complet |
| — | 22+ écrans TUI dans `app.py` | detection, mounts, kernel, initramfs, presets, coherence, snapshots, stream, config, debug, zbm, graph, crosscompile, multiarch, security, intentlog, metrics, modules, config_snapshot, error_log, history, monitoring |
| — | `role_patterns.py` — 15+ rôles | Scoring agrégé multi-signaux (pattern 40%, magic 30%, content 20%, partition 10%) |
| — | Config 19 sections (configobj) | Recherche multi-chemins, validation configspec, chmod 640 |
| — | `launch.sh` complet | APT + DKMS + venv + sudoers + branche `dev` + `--run`/`--no-run` |
| — | Multi-init (systemd/OpenRC/sysvinit/upstart) | Scripts contrib + `ServiceInstallTask` + `detect_init()` |
| — | Bridge tickets (UI ↔ Scheduler) | `lib/ui/bridge.py` + `lib/scheduler/bridge.py`, thread-safe |
| — | Intents câblés | `pool.import_all`, `pool.status`, `mount.request`, `pool.import`, `init.detect`, `init.install`, `init.configure`, `integration.test` |
| — | `DetectionScreen` fonctionnel | pool.import_all → pool.status → dataset listing → probe parallèle |
| — | GraphViewScreen | Animation 10 FPS, auto-centrage, pause, navigation temporelle |
| — | Tests | `test_scheduler_bridge.py`, `test_bridge.py`, tests intégration multi-distro |
| — | Documentation | DIAGRAMS, GRAPHVIEW, bridge docs, manuel, INDEX, SESSION_FINAL |
| 7.0 | launch.sh branche `dev` par défaut | Corrigé |
| 8.1a+b | Scheduler↔bridge unifié | — |
| 10.1 | Unicode `detection.py` | Escape sequences `\u2705` etc. |
| 10.3 | `LoggedDummyBridge` | — |
| 10.4 | `welcome.py` lazy imports | — |
| 16.20+21 | Intents `mount.request` + `pool.import` | — |
| 16.50-54 | Doublons intents + cli.py corrigé | — |
| 17.7 | `pyproject.toml` | — |
| Phase 1-6 | Stabilisation TUI, robustesse, fonctionnalités, init/, tests, nettoyage | Voir `next_actions.md` historique |

---

## 🚧 Tâche active — 10.5

Supprimer 3 fichiers doublons inutilisés :
1. `fsdeploy/lib/ui/screens/graph_enhanced.py` — doublon de `graph.py`
2. `fsdeploy/lib/ui/screens/security_enhanced.py` — doublon de `security.py`
3. `fsdeploy/lib/ui/screens/navigation.py` — code mort

Détails dans `add.md`.

---

## ⏳ Restant — Vue d'ensemble

| Phase | ID | Description | Priorité | Statut |
|-------|----|-------------|----------|--------|
| **10 UI** | 10.2 | Vérifier tous les écrans Textual 8.x (no `self.name=`, `Select.NULL`, `on_data_table_row_highlighted`) | P0 | À faire |
| **10 UI** | 10.5 | Supprimer doublons écrans | P0 | **En cours** |
| **10 UI** | 10.6 | Câbler `MountsScreen` callbacks `_on_mount_done` vers bridge réel | P1 | À faire |
| **10 UI** | 10.7 | Câbler `KernelScreen` — sélection/compilation via intents | P1 | À faire |
| **10 UI** | 10.8 | Câbler `InitramfsScreen` — génération via intents | P1 | À faire |
| **10 UI** | 10.9 | Câbler `PresetsScreen` — CRUD presets JSON | P1 | À faire |
| **10 UI** | 10.10 | Câbler `StreamScreen` — ffmpeg RTMP via intents | P1 | À faire |
| **9 launch.sh** | 9.1 | `linux-headers` dynamique (uname -r) au lieu de `linux-headers-amd64` hardcodé | P0 | À faire |
| **9 launch.sh** | 9.2 | Gestion erreurs DKMS (timeout, fallback) | P1 | À faire |
| **11 Overlay** | 11.1 | SquashFS mount/unmount tasks | P1 | À faire |
| **11 Overlay** | 11.2 | Overlay filesystem (overlayfs) setup | P1 | À faire |
| **11 Overlay** | 11.3 | Switch rootfs à chaud | P1 | À faire |
| **16 Câblage** | 16.1 | Intents kernel : `kernel.list`, `kernel.select`, `kernel.compile` | P1 | À faire |
| **16 Câblage** | 16.2 | Intents initramfs : `initramfs.generate`, `initramfs.select` | P1 | À faire |
| **16 Câblage** | 16.3 | Intents presets : `preset.create`, `preset.apply`, `preset.delete` | P1 | À faire |
| **16 Câblage** | 16.4 | Intents coherence : `coherence.check`, `coherence.fix` | P1 | À faire |
| **16 Câblage** | 16.5 | Intents snapshots : `snapshot.create`, `snapshot.rollback`, `snapshot.list` | P1 | À faire |
| **16 Câblage** | 16.6 | Intents stream : `stream.start`, `stream.stop`, `stream.status` | P1 | À faire |
| **16 Câblage** | 16.7 | Intents ZBM : `zbm.install`, `zbm.configure`, `zbm.verify` | P1 | À faire |
| **16 Câblage** | 16.8 | Intents rootfs switch : `rootfs.switch`, `rootfs.overlay` | P2 | À faire |
| **16 Câblage** | 16.9 | Intents modules hotplug : `module.load`, `module.unload` | P2 | À faire |
| **16 Câblage** | 16.10 | Bus sources réels : InotifySource, UdevSource, SocketSource | P2 | À faire |
| **17 Sécurité** | 17.1 | SecurityResolver complet — tous les niveaux (allow/deny/require_sudo/dry_run_only) | P0 | À faire |
| **17 Sécurité** | 17.2 | Sudoers validation (`visudo -cf`) | P0 | À faire |
| **17 Sécurité** | 17.3 | `_has_privilege()` vérification effective | P0 | À faire |
| **17 Sécurité** | 17.4 | Audit sécurité des tasks (pas de shell injection) | P0 | À faire |
| **18 Tests** | 18.1 | Tests unitaires pour chaque intent | P1 | À faire |
| **18 Tests** | 18.2 | Tests intégration scheduler complet (event → task completion) | P1 | À faire |
| **18 Tests** | 18.3 | Tests TUI avec Textual Pilot | P2 | À faire |
| **7 Audit** | 7.1 | `live/setup.py` — `linux-headers` dynamique | P0 | À faire |
| **7 Audit** | 7.2 | Sync `tests/` stale copies | P1 | À faire |
| **7 Audit** | 7.3 | Refresh docs (next_actions, README, DIAGRAMS) | P1 | À faire |
| **7 Audit** | 7.4 | `lib/function/module/registry.py` stub → re-export ou supprimer | P2 | À faire |

---

## Ordre recommandé

1. **10.5** ← en cours (doublons)
2. **10.2** — audit Textual 8.x compatibilité tous écrans
3. **17.1-17.4** — sécurité (P0, critique avant tout usage réel)
4. **9.1** — linux-headers dynamique
5. **7.1** — live/setup.py headers dynamique
6. **16.1-16.7** — câblage intents (kernel, initramfs, presets, coherence, snapshots, stream, zbm)
7. **10.6-10.10** — câblage UI ↔ intents
8. **11.1-11.3** — overlay/squashfs/rootfs switch
9. **18.1-18.3** — tests
10. **16.8-16.10** — fonctionnalités avancées (rootfs switch, modules hotplug, bus sources)

---

## Compteur fichiers Python estimé

| Répertoire | Fichiers | Lignes (approx.) |
|------------|----------|-------------------|
| `lib/scheduler/` | ~12 | ~2500 |
| `lib/ui/screens/` | ~22 | ~4000 |
| `lib/ui/` (app, bridge) | 2 | ~600 |
| `lib/function/` | ~15 | ~2000 |
| `lib/intents/` | ~8 | ~800 |
| `lib/bus/` | ~4 | ~400 |
| `lib/` (daemon, config, log, diagnostic) | 4 | ~1200 |
| `tests/` | ~10 | ~800 |
| **Total** | **~77** | **~12300** |