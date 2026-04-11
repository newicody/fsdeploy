# Suivi des actions prioritaires

**Date de début** : 2026-04-09
**Dernière mise à jour** : 2026-04-11
**Responsable** : équipe de développement

## Actions P0

### 1. BridgeScreenMixin — ✅ Terminé
### 1.1 Intégration bridge dans les écrans — ✅ Terminé
- Tous les écrans lib/ utilisent `@property def bridge` → `getattr(self.app, "bridge", None)`
- Copies `tests/` encore désynchronisées (priorité basse, action 1.4)

### 1.2 Corriger imports navigation.py — ✅ Terminé
- **Fichier** : `fsdeploy/lib/ui/screens/navigation.py`
- **Description** : Remplacer `cross_compile_screen` → `crosscompile`, `multiarch_screen` → `multiarch`
- **Statut** : ✅ Terminé
- **Date réal.** : 2026-04-11

### 1.3 Stub ModuleRegistry cassé ← PROCHAINE
- **Fichiers** : `lib/ui/screens/module_registry.py`, `lib/function/module/registry.py`
- **Statut** : À faire
- **Date cible** : 2026-04-13

### 2. Mode dry-run
- **Fichiers** : `__main__.py`, `lib/daemon.py`, toutes les tâches
- **Statut** : À faire
- **Date cible** : 2026-04-13

### 3. Health-check au démarrage
- **Fichiers** : `lib/intents/system_intent.py`, `lib/ui/screens/welcome.py`
- **Statut** : À faire
- **Date cible** : 2026-04-14

### 4. MountManager avec journal et cleanup
- **Fichiers** : `lib/function/mount/manager.py` (nouveau), `lib/daemon.py`
- **Statut** : À faire
- **Date cible** : 2026-04-15

## Actions P1

### 5. Notifications TUI unifiées — À faire
### 6. Export/import de configuration — À faire
### 7. Mode recovery — À faire
### 8. Métriques de performance — À faire

## Journal des décisions

| Date | Événement |
|------|-----------|
| 2026-04-09 | Analyse du projet et priorisation. |
| 2026-04-10 | Audit partiel, corrections bridge. |
| 2026-04-11 | Action 1.1 terminée (3 écrans enhanced/detection corrigés). Prochaine : 1.2 navigation.py. |
