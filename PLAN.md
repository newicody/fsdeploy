# PLAN — fsdeploy (branche dev)

**Dernière mise à jour** : 2026-04-11

## Phase 1 : Stabilisation TUI — ✅ TERMINÉE

- [x] 1.0–1.3 Tous terminés
- [ ] 1.4 Synchroniser copies `tests/` avec `lib/` (priorité basse, différé)

## Phase 2 : Robustesse (en cours)

- [x] 2.0 Mode `--dry-run`
- [x] 2.1 Health-check au démarrage
- [x] 2.2 MountManager avec journal et cleanup
- [x] 2.3 Notifications TUI unifiées via bridge → `app.notify()` ← PROCHAINE

## Phase 3 : Fonctionnalités

- [ ] 3.0 Export/import configuration (presets JSON étendus)
- [ ] 3.1 Mode recovery (`--recovery`)
- [ ] 3.2 Métriques de performance
- [ ] 3.3 GraphViewScreen câblé sur données live
- [ ] 3.4 FileHandler pour logs persistants

## Phase 4 : Intégration init/

- [ ] 4.0–4.7 (inchangé)

## Phase 5 : Tests complets

- [ ] 5.0–5.2 (inchangé)
