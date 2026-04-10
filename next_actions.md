# Suivi des actions prioritaires

**Date de début** : 2026-04-09
**Dernière mise à jour** : 2026-04-10
**Responsable** : équipe de développement

## Actions P0

### 1. BridgeScreenMixin
- **Fichiers** : `lib/ui/mixins.py`, tous les écrans
- **Statut** : ✅ Terminé

### 1.1 Intégration bridge dans les écrans
- **Statut** : ⚠️ Partiellement terminé
- **Détail** :
  - `moduleregistry_screen.py` (lib/) : ✅ déjà corrigé (property bridge)
  - `cross_compile_screen.py` (lib/) : ❌ import direct + class-level `SchedulerBridge.default()`
  - `multiarch_screen.py` : ✅ n'existe pas, `multiarch.py` est déjà OK
  - copies `tests/` : ❌ `tests/.../moduleregistry_screen.py` et `tests/.../crosscompile.py` ont encore l'import direct
- **Reste** : corriger `cross_compile_screen.py` + synchro tests/
- **Date cible** : 2026-04-10

### 1.2 Nettoyage doublons écrans (NOUVEAU)
- **Fichiers** : `navigation.py`, `cross_compile_screen.py`, `moduleregistry_screen.py`
- **Description** : `navigation.py` importe des variantes `_screen` qui dupliquent les écrans enregistrés dans `app.py` screen_map (`crosscompile.py`, `multiarch.py`, `module_registry.py`). Unifier : un seul fichier par écran, `navigation.py` pointe vers les bons.
- **Statut** : À faire
- **Date cible** : 2026-04-11

### 1.3 Stub ModuleRegistry cassé (NOUVEAU)
- **Fichiers** : `lib/ui/screens/module_registry.py`, `lib/function/module/registry.py`
- **Description** : `module_registry.py` importe `ModuleRegistry` qui est un stub vide. Crash garanti au mount. Passer l'écran au bridge ou implémenter le registre.
- **Statut** : À faire
- **Date cible** : 2026-04-12

### 2. Mode dry-run
- **Fichiers** : `__main__.py`, `lib/daemon.py`, toutes les tâches
- **Statut** : À faire
- **Date cible** : 2026-04-12

### 3. Health-check au démarrage
- **Fichiers** : `lib/intents/system_intent.py`, `lib/ui/screens/welcome.py`
- **Statut** : À faire
- **Date cible** : 2026-04-13

### 4. MountManager avec journal et cleanup
- **Fichiers** : `lib/function/mount/manager.py` (nouveau), `lib/daemon.py`
- **Statut** : À faire
- **Date cible** : 2026-04-14

## Actions P1

### 5. Notifications TUI unifiées
- **Fichiers** : `lib/ui/app.py`
- **Statut** : À faire

### 6. Export/import de configuration
- **Fichiers** : `lib/intents/system_intent.py`, `lib/ui/screens/presets.py`
- **Statut** : À faire

### 7. Mode recovery
- **Fichiers** : `__main__.py`, `lib/intents/system_intent.py`
- **Statut** : À faire

### 8. Métriques de performance
- **Fichiers** : MetricsScreen, scheduler
- **Statut** : À faire

## Journal des décisions

| Date | Événement |
|------|-----------|
| 2026-04-09 | Analyse du projet et priorisation. |
| 2026-04-10 | Audit : `moduleregistry_screen.py` déjà OK, `multiarch_screen.py` inexistant, doublons écrans + stub ModuleRegistry identifiés. |
