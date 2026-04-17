# PLAN.md — fsdeploy (branche `dev`)

> **Dernière mise à jour** : 2026-04-17
> **Tâche active** : **8.1** — Unification scheduler ↔ bridge global
> **Worker** : `worker.py` consomme `add.md`

---

## Conventions

ID stable · `⏳` `🚧` `✅` `⏸️` `❌` · P0-P3 · un seul `🚧` à la fois

---

## 🚧 Tâche active — 8.1

Unification scheduler ↔ bridge global — voir `add.md`.

---

## 📋 Phase 8 — Scheduler

| ID | Description | Prio | Statut |
|----|-------------|------|--------|
| 8.1 | Unification scheduler ↔ bridge (`_global_instance`, `_bridge_ticket` propagation) | P0 | 🚧 |
| 8.2 | Réveil immédiat `event_queue.put` (`_wakeup` Event) | P1 | ⏳ |
| 8.3 | `_process_waiting` event-driven (après `release_locks` uniquement) | P2 | ⏳ |
| 8.4 | Renommer `Intent.resolve()` → `Intent.expand()` | P2 | ⏳ |

---

## 📋 Phase 9 — launch.sh

| ID | Description | Prio | Statut |
|----|-------------|------|--------|
| 9.1 | `_is_live()` retirer heuristique fstab, exiger ≥ 2 indicateurs | P0 | ⏳ |
| 9.2 | Support APT deb822 (`debian.sources`) + Python `live/setup.py` | P0 | ⏳ |
| 9.3 | `_wait_dkms()` matcher `$(uname -r)` strictement | P1 | ⏳ |
| 9.4 | Sudoers filtrés `command -v` | P1 | ⏳ |
| 9.5 | `trap ERR` + restauration `sources.list.bak` | P1 | ⏳ |
| 9.6 | Défaut `RUN_AFTER=0` | P2 | ⏳ |
| 9.7 | ACL venv `setfacl -d` | P2 | ⏳ |
| 9.8 | `--update` régénérer wrappers | P1 | ⏳ |
| 9.9 | `--update` vérifier exit pip avant `exec` | P1 | ⏳ |
| 9.10 | Vérif espace disque (512 Mo min) | P2 | ⏳ |
| 9.11 | Lock concurrent `flock` | P2 | ⏳ |

---

## 📋 Phase 10 — UI correctifs critiques

| ID | Description | Prio | Statut |
|----|-------------|------|--------|
| 10.1 | Escape Unicode `detection.py` `"2705"` → `"\u2705"` | P0 | ⏳ |
| 10.2 | Uniformiser imports écrans, supprimer `ui/screens/__init__.py` racine | P0 | ⏳ |
| 10.3 | `DummyBridge` log warning | P0 | ⏳ |
| 10.4 | `welcome.py` imports lazy (pas top-level) | P0 | ⏳ |
| 10.5 | Supprimer doublons (`multiarch*`, `graph*`, `security*`) | P0 | ⏳ |
| 10.6 | `MultiArchScreen` bridge class attr → `@property` | P1 | ⏳ |
| 10.7 | `ConfigSnapshotScreen` via bridge.emit | P1 | ⏳ |
| 10.8 | `NavigationScreen` enregistrer ou supprimer | P2 | ⏳ |
| 10.9 | Bindings `e/l/u/z` manquants | P1 | ⏳ |
| 10.10 | `_refresh_from_store` erreurs uniquement | P1 | ⏳ |

---

## 📋 Phase 11 — Overlay sécurisé

| ID | Description | Prio | Statut |
|----|-------------|------|--------|
| 11.1 | `OverlayProfile` dataclass + `.fsdeploy-overlay-meta` (MD5 lower, kernel, timestamps) | P0 | ⏳ |
| 11.2 | `OverlayValidator` task (meta↔lower MD5, `work/` propre, modules↔kernel) | P0 | ⏳ |
| 11.3 | MountsScreen section overlay (profils, associations, anti-mélange) | P0 | ⏳ |
| 11.4 | CoherenceScreen check overlay profil | P1 | ⏳ |
| 11.5 | `work/` cleanup avant remontage | P1 | ⏳ |
| 11.6 | Multi-système (N presets = N profils, pas de croisement) | P2 | ⏳ |

---

## 📋 Phase 12 — Bus

| ID | Description | Prio | Statut |
|----|-------------|------|--------|
| 12.1 | Éliminer bypass security (`message_bus.emit` → `event_queue.put`) | P1 | ⏳ |
| 12.2 | InotifySource : surveiller `boot_mount` config, pas `/boot` | P1 | ⏳ |
| 12.3 | Intents pour `timer.coherence_check` / `timer.scrub_check` | P1 | ⏳ |
| 12.4 | SocketSource validation taille/timeout | P2 | ⏳ |
| 12.5 | `_event_queue_ref` → attribut instance | P2 | ⏳ |

---

## 📋 Phase 13 — Logs

| ID | Description | Prio | Statut |
|----|-------------|------|--------|
| 13.1 | Supprimer `lib/util/logging.py` doublon | P1 | ⏳ |
| 13.2 | `HuffmanStore` persistence disque (flush) | P1 | ⏳ |
| 13.3 | Daemon passer `log_dir` à `setup_logging` | P1 | ⏳ |
| 13.4 | `RotatingFileHandler` dans `lib/log.py` | P2 | ⏳ |

---

## 📋 Phase 14 — Config

| ID | Description | Prio | Statut |
|----|-------------|------|--------|
| 14.1 | `DEBIAN_PACKAGES` : `linux-headers-amd64` → dynamique | P1 | ⏳ |
| 14.2 | `live/setup.py` parser deb822 (unifier avec 9.2) | P1 | ⏳ |
| 14.3 | Thread-safety `FsDeployConfig` (Lock sur `set/save`) | P2 | ⏳ |

---

## 📋 Phase 15 — UI fonctionnalités spec

| ID | Description | Prio | Statut |
|----|-------------|------|--------|
| 15.1 | Écran Network | P2 | ⏳ |
| 15.2 | Hot-switch kernel/rootfs (kexec) | P2 | ⏳ |
| 15.3 | InitramfsScreen toggle Python stream | P2 | ⏳ |
| 15.4 | CoherenceScreen simulation boot | P3 | ⏳ |
| 15.5 | ZBMScreen bouton reboot | P3 | ⏳ |

---

## 📋 Phase 16 — Câblage lib ↔ UI (intents manquants / écrans stubs)

**Constat** : 18 intents enregistrés ne sont jamais émis depuis l'UI, 6 events UI n'ont pas d'intent, 7 tasks n'ont ni intent ni chemin UI, 5 écrans sont des stubs vides, 1 doublon d'intent.

### A — Intents existants à câbler dans les écrans

| ID | Intent | Écran cible | Action UI à ajouter | Prio | Statut |
|----|--------|-------------|---------------------|------|--------|
| 16.1 | `kernel.registry.scan` | KernelScreen | Bouton « Scanner tous les datasets » | P1 | ⏳ |
| 16.2 | `kernel.provision` | KernelScreen | Bouton « Provisionner » sur kernel sélectionné | P1 | ⏳ |
| 16.3 | `kernel.unprovision` | KernelScreen | Bouton « Retirer » sur kernel provisionné | P1 | ⏳ |
| 16.4 | `kernel.mainline.detect` | KernelScreen | Bouton « Détecter kernel mainline » | P2 | ⏳ |
| 16.5 | `zbm.validate` | ZBMScreen | Bouton « Preflight check » (standalone, pas inline coherence) | P1 | ⏳ |
| 16.6 | `coherence.quick` | CoherenceScreen | Bouton « Vérif rapide » à côté de « Vérif complète » | P2 | ⏳ |
| 16.7 | `scheduler.verify` | DebugScreen | Bouton « Vérifier scheduler » | P1 | ⏳ |
| 16.8 | `security.status` | SecurityScreen | Remplacer table hardcodée par `bridge.emit("security.status")` | P1 | ⏳ |
| 16.9 | `init.detect` | WelcomeScreen | Appeler via bridge au lieu du code local `_detect_init_system()` | P2 | ⏳ |
| 16.10 | `kernel.module.detect` | ModuleRegistryScreen | Bouton « Scanner modules » remplace table hardcodée | P1 | ⏳ |
| 16.11 | `kernel.module.integrate` | ModuleRegistryScreen | Bouton « Intégrer dans initramfs » | P1 | ⏳ |
| 16.12 | `integration.test` | DebugScreen | Bouton « Test intégration » | P2 | ⏳ |
| 16.13 | `init.boot.config` | (nouveau InitConfigScreen ou dans Config) | Éditer params boot init (modules, cmdline) | P2 | ⏳ |
| 16.14 | `init.upstart_sysv.install` / `test` | (nouveau InitServiceScreen ou dans Config) | Installer/tester service init | P2 | ⏳ |
| 16.15 | `zfsbootmenu.integrate` | ZBMScreen | Bouton « Intégration complète ZBM » (full workflow) | P2 | ⏳ |
| 16.16 | `config.snapshot.*` | ConfigSnapshotScreen | Remplacer import direct par `bridge.emit` (= 10.7) | P1 | ⏳ |

### B — Events UI sans intent — créer les intents manquants

| ID | Event UI | Écran source | Intent à créer | Prio | Statut |
|----|----------|-------------|----------------|------|--------|
| 16.20 | `mount.request` | MountsScreen | `@register_intent("mount.request")` → `DatasetMountTask` | P0 | ⏳ |
| 16.21 | `pool.import` (un seul pool) | DetectionScreen | `@register_intent("pool.import")` → `PoolImportTask` | P0 | ⏳ |
| 16.22 | `module_registry.load` | ModuleRegistryScreen | `@register_intent("module_registry.load")` → `ModuleRegistryLoadTask` (ou câbler via 16.10) | P1 | ⏳ |
| 16.23 | `partition.detect` | PartitionDetectionScreen | `@register_intent("partition.detect")` → `PartitionDetectTask` (existe déjà dans `detection_intent.py`, juste manque le binding event name) | P1 | ⏳ |
| 16.24 | `multiarch.sync` / `multiarch.list` | MultiArchScreen | Soit créer les intents, soit convertir l'écran en bridge vers `kernel.registry.scan` filtré par arch | P2 | ⏳ |

### C — Tasks orphelines — créer intents + câbler UI

| ID | Task | Intent à créer | Écran cible | Prio | Statut |
|----|------|----------------|-------------|------|--------|
| 16.30 | `RootfsSwitchTask` | `rootfs.switch` | MountsScreen (mode booted) ou OverlayScreen (Phase 11) | P1 | ⏳ |
| 16.31 | `RootfsMountTask` | `rootfs.mount` | MountsScreen section overlay | P1 | ⏳ |
| 16.32 | `RootfsUpdateTask` | `rootfs.update` | MountsScreen (rebuild squashfs) | P2 | ⏳ |
| 16.33 | `NetworkSetupTask` | `network.setup` | NetworkScreen (Phase 15.1) | P2 | ⏳ |
| 16.34 | `LiveSetupTask` | `live.setup` | WelcomeScreen (mode deploy, bouton « Setup live ») | P2 | ⏳ |
| 16.35 | `EnvironmentDetectTask` | `environment.detect` | WelcomeScreen (remplacer code local) | P2 | ⏳ |
| 16.36 | `ServiceInstallTask` | `service.install` | ConfigScreen ou InitServiceScreen | P2 | ⏳ |

### D — Écrans stubs à compléter ou supprimer

| ID | Écran | Action | Prio | Statut |
|----|-------|--------|------|--------|
| 16.40 | `CrossCompileScreen` | Câbler vers `kernel.compile` avec params cross-compile (`arch`, `toolchain`) ou supprimer | P2 | ⏳ |
| 16.41 | `MultiArchScreen` (simple) | Fusionner avec `multiarch_screen.py` ; câbler vers `kernel.registry.scan` filtré par arch | P2 | ⏳ |
| 16.42 | `ModuleRegistryScreen` | Câbler vers `kernel.module.detect` + `kernel.module.integrate` (16.10/16.11) | P1 | ⏳ |
| 16.43 | `PartitionDetectionScreen` | Câbler vers `partition.detect` intent (16.23) | P1 | ⏳ |
| 16.44 | `NavigationScreen` | Supprimer (code mort, jamais atteignable) | P1 | ⏳ |

### E — Doublon intent

| ID | Problème | Fix | Prio | Statut |
|----|----------|-----|------|--------|
| 16.50 | `config.snapshot.*` défini dans `system_intent.py` ET `config_intent.py` | Supprimer de l'un des deux (garder `system_intent.py`, supprimer `config_intent.py` ou l'inverse) | P0 | ⏳ |

---

## ✅ Historique

Phase 7 (terminée 2026-04-15) · Phases 1-6 (terminées avant 2026-04-09)

## Journal

| Date | Événement |
|------|-----------|
| 2026-04-09 | Début Phase 1 |
| 2026-04-15 | Phase 7 clôturée (v1.0.0) |
| 2026-04-16 | Phases 8-10 définies |
| 2026-04-17 | Phases 11-15 (overlay, bus, logs, config, UI spec) |
| 2026-04-17 | Phase 16 : audit lib↔UI — 18 intents non câblés, 6 events sans intent, 7 tasks orphelines, 5 écrans stubs, 1 doublon |