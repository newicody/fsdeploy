# Plan de développement fsdeploy — État réel

**Dernière mise à jour** : 2026-04-10
**Branche** : dev
**Itération** : 8

---

## Diagnostic révisé (post-push dev)

### Ce qui fonctionne
- Architecture event->intent->task complète
- Daemon, config, codec, runtime, executor, bridge, log, CLI
- Migration Textual 8.2.1 effectuée
- Bugfixes critiques portés (factory closures, SocketSource, threading, Screen.name)
- **BridgeScreenMixin** créé dans `lib/ui/mixins.py` (action 1 terminée)

### Écrans déjà bien câblés au bridge
- `detection.py` : pipeline 4 phases complet (import->pools->datasets->probes), factory callbacks
- `mounts.py` : factory callbacks (`_make_mount_callback`, etc.), `_on_mount_done` / `_on_umount_done`
- `coherence.py` : `bridge.emit("coherence.quick")` avec callback
- `presets.py` : `bridge.emit("presets.save")` / `bridge.emit("presets.activate")`
- `stream.py` : property `bridge` via `self.app.bridge` — pattern correct

### Violations d'architecture détectées
- `cross_compile_screen.py` : **import direct** `from fsdeploy.lib.scheduler.bridge import SchedulerBridge` + `SchedulerBridge.default()` class-level
- `multiarch_screen.py` : même violation
- `moduleregistry_screen.py` : probablement même violation

Ces écrans doivent utiliser `self.app.bridge` comme les autres.

---

## [Fait]

- Architecture event->intent->task pipeline complet
- Daemon, config(19 sections), codec(HuffmanStore), runtime(thread-safe), executor(ThreadPool), bridge(tickets), log(structlog+ASCII)
- CLI typer 4 sous-commandes
- launch.sh bootstrap complet
- Migration Textual 8.2.1
- Bugfixes critiques
- BridgeScreenMixin (`lib/ui/mixins.py`)
- Écrans detection/mounts/coherence/presets/stream câblés

---

## [En cours] — Action 1.1 : Intégration mixin dans les écrans

Correction des 3 écrans qui violent l'isolation TUI/lib :

| Fichier | Problème | Correction |
|---------|----------|------------|
| `lib/ui/screens/cross_compile_screen.py` | Import direct SchedulerBridge | Utiliser `self.app.bridge` via property |
| `lib/ui/screens/multiarch_screen.py` | Import direct SchedulerBridge | Idem |
| `lib/ui/screens/moduleregistry_screen.py` | Import direct SchedulerBridge | Idem (à vérifier) |

---

## [À faire]

### P0 — Bloquants

| # | Action | Statut | Cible |
|---|--------|--------|-------|
| 1 | BridgeScreenMixin | **Terminé** | 2026-04-10 |
| 1.1 | Intégration mixin dans écrans | **En cours** | 2026-04-11 |
| 2 | Mode `--dry-run` | À faire | 2026-04-11 |
| 3 | Health-check au démarrage | À faire | 2026-04-12 |
| 4 | MountManager journal/cleanup | À faire | 2026-04-13 |

### P1 — Fonctionnels

| # | Action | Statut | Cible |
|---|--------|--------|-------|
| 5 | Notifications TUI unifiées | À faire | 2026-04-14 |
| 6 | Export/import config | À faire | 2026-04-15 |
| 7 | Mode recovery | À faire | 2026-04-16 |
| 8 | Métriques performance | À faire | 2026-04-17 |

### P2 — Améliorations

- GraphViewScreen câblé données live
- StreamScreen ffmpeg RTMP réel
- ConfigScreen éditeur fonctionnel
- DebugScreen logs/tasks/state temps réel
- Cross-compilation tests aarch64
- Purge CLEANUP.md
- FileHandler dans setup_logging()
- Wrapper fsdeploy-web (`textual serve`)
- Intégration `init/` -> `lib/function/`
- Tests : compléter test_all.py (30 tests)

### P3 — Polish

- Documentation utilisateur (manuel.md)
- CI/CD GitHub Actions
- Presets stream (boot sans rootfs)
- Hot-swap noyau/modules/rootfs

---

## Principes

- **Zéro import de `lib/` dans les écrans TUI** : tout via `self.app.bridge`
- **`mount -t zfs`** : forme canonique
- **Factory closures** : obligatoires pour callbacks dans boucles
- **Purger `__pycache__`** : après tout remplacement
- **Fichiers complets** : jamais de patches
- **`configobj`** : pas pydantic/dataclasses
- **Trois contextes** : Debian Live / initramfs / système booté