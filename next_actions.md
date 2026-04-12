# Suivi des actions prioritaires

**Date de début** : 2026-04-09
**Dernière mise à jour** : 2026-04-13

---

## Historique (Phases 1–6) — ✅ TERMINÉ

Toutes les phases précédentes sont terminées :
- Phase 1 : Stabilisation TUI (BridgeScreenMixin, navigation, ModuleRegistry)
- Phase 2 : Robustesse (dry-run, health-check, MountManager, notifications)
- Phase 3 : Fonctionnalités (config export, recovery, métriques, state_snapshot, log_dir)
- Phase 4 : Intégration init/ (live, boot, rootfs, network, initramfs, environment, service)
- Phase 5 : Tests (test_all, test_intents_build, test_screens_integration)
- Phase 6 : Nettoyage (module_registry unifié, re-exports, cross_compile_screen supprimé)

---

## Phase 7 — Audit post-completion

### 7.0 launch.sh : branche par défaut ← PROCHAINE
- **Fichier** : `fsdeploy/launch.sh`
- **Bug** : `REPO_BRANCH` défaut `main` → clone du code obsolète
- **Fix** : Changer en `dev`, ajouter lancement auto post-install
- **Priorité** : P0 (bloque l'installation pour tout nouvel utilisateur)
- **État** : ✅ **Corrigé** (branche dev, options --run/--no-run ajoutées)

### 7.1 live/setup.py : linux-headers dynamique
- **Fichier** : `fsdeploy/lib/function/live/setup.py`
- **Bug** : `linux-headers-amd64` hardcodé dans `DEBIAN_PACKAGES`
- **Fix** : Détection dynamique via `uname -r`
- **Priorité** : P0 (freeze DKMS potentiel)

### 7.2 Sync tests/ stale copies
- **Fichiers** : `tests/fsdeploy/lib/ui/screens/cross_compile_screen.py`, `moduleregistry_screen.py`
- **Fix** : Remplacer par re-exports ou supprimer
- **Priorité** : P1
- **État** : ⏳ **En attente** (besoin d'ajouter les fichiers au chat pour modification)

### 7.2a Demande d'ajout des fichiers tests
- **Objectif** : Ajouter `tests/fsdeploy/lib/ui/screens/cross_compile_screen.py` et `tests/fsdeploy/lib/ui/screens/moduleregistry_screen.py` au chat pour permettre les modifications.
- **Action** : Veuillez ajouter ces fichiers au chat via un message utilisateur.
- **Priorité** : P0 (bloque 7.2)

### 7.3 next_actions.md + docs refresh
- **Fichiers** : `next_actions.md`, `README.md`, `DIAGRAMS.md`, `fsdeploy_main_status.md`
- **Fix** : Réécriture cohérente avec l'état actuel
- **Priorité** : P1

### 7.4 lib/function/module/registry.py stub
- **Fichier** : `fsdeploy/lib/function/module/registry.py`
- **Fix** : Re-export depuis `lib/modules/registry.py` ou supprimer
- **Priorité** : P2

---

## Journal des décisions

| Date | Événement |
|------|-----------|
| 2026-04-09 | Priorisation initiale, début Phase 1 |
| 2026-04-10 | Corrections bridge écrans |
| 2026-04-11 | Phase 1 terminée, début Phase 2 |
| 2026-04-12 | Phases 2–6 terminées. Audit complet → Phase 7 identifiée |
| 2026-04-12 | launch.sh : branche `main` par défaut = bug bloquant identifié |
| 2026-04-12 | 7.0 corrigé (branch=dev, --run/--no-run ajoutées) |
| 2026-04-13 | Demande d'ajout des fichiers tests pour 7.2 |
