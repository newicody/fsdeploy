# PLAN — fsdeploy (branche dev)

**Dernière mise à jour** : 2026-04-12

## Phase 1 : Stabilisation TUI — ✅ TERMINÉE
## Phase 2 : Robustesse — ✅ TERMINÉE

## Phase 3 : Fonctionnalités (en cours)

- [x] 3.0 Export/import configuration
- [x] 3.1 Mode recovery (`--recovery`)
- [x] 3.2 Métriques de performance
- [x] 3.3 Scheduler.state_snapshot() pour GraphViewScreen
- [ ] 3.4 Passer log_dir à setup_logging() depuis __main__.py ← PROCHAINE

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