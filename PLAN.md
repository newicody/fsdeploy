# PLAN — fsdeploy (branche dev)

**Dernière mise à jour** : 2026-04-11

## Phase 1 : Stabilisation TUI (en cours)

- [x] 1.0 BridgeScreenMixin créé
- [x] 1.1 Corriger imports directs bridge dans TOUS les écrans
- [x] 1.2 Corriger navigation.py : imports `_screen` → écrans canoniques
- [ ] 1.3 Résoudre stub `ModuleRegistry` (crash au mount de `module_registry.py`)
- [ ] 1.4 Synchroniser copies `tests/` avec `lib/`

## Phase 2 : Robustesse

- [ ] 2.0 Mode `--dry-run` (CLI + propagation dans toutes les tasks)
- [ ] 2.1 Health-check au démarrage (ZFS, permissions, espace disque)
- [ ] 2.2 MountManager avec journal et cleanup automatique
- [ ] 2.3 Notifications TUI unifiées via bridge → `app.notify()`

## Phase 3 : Fonctionnalités

- [ ] 3.0 Export/import configuration (presets JSON étendus)
- [ ] 3.1 Mode recovery (`--recovery`)
- [ ] 3.2 Métriques de performance (durée, succès/échec par task)
- [ ] 3.3 GraphViewScreen câblé sur données live (`get_state_snapshot()`)
- [ ] 3.4 FileHandler dans `setup_logging()` pour logs persistants

## Phase 4 : Intégration init/

- [ ] 4.0 `live_setup` → `lib/function/live/setup.py`
- [ ] 4.1 `init_script` → `lib/function/boot/init.py`
- [ ] 4.2 `switch` → enrichit `lib/function/rootfs/switch.py`
- [ ] 4.3 `network` → `lib/function/network/setup.py`
- [ ] 4.4 `initramfs_hook` → `lib/function/boot/initramfs.py`
- [ ] 4.5 `entry` → `lib/intents/boot_intent.py`
- [ ] 4.6 `environment` → `lib/function/detect/environment.py`
- [ ] 4.7 `services` → `lib/function/service/`

## Phase 5 : Tests complets

- [ ] 5.0 `test_all.py` (30 tests couvrant tous les layers)
- [ ] 5.1 Tests unitaires pour chaque intent
- [ ] 5.2 Tests d'intégration TUI (textual pilot)
