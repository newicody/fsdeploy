# Suivi des actions prioritaires

**Date de début** : 2026-04-09
**Dernière mise à jour** : 2026-04-11
**Responsable** : équipe de développement

## Actions P0

### 1. BridgeScreenMixin
- **Statut** : ✅ Terminé

### 1.1 Intégration bridge dans les écrans
- **Statut** : ⚠️ Partiellement terminé
- **Détail audit 2026-04-11** :
  - `crosscompile.py` : ✅ OK (property bridge)
  - `cross_compile_screen.py` : ✅ corrigé (property bridge)
  - `multiarch.py` : ✅ OK (property bridge)
  - `moduleregistry_screen.py` : ✅ OK (property bridge)
  - `graph_enhanced.py` : ❌ `from ...bridge import SchedulerBridge` + `bridge = SchedulerBridge.default()`
  - `security_enhanced.py` : ❌ `from ...bridge import SchedulerBridge` + `bridge = SchedulerBridge.default()`
  - `partition_detection.py` : ❌ `from ...bridge import SchedulerBridge` + `bridge = SchedulerBridge.default()`
  - copies `tests/` : ❌ multiples fichiers encore cassés
- **Reste à faire** : corriger `graph_enhanced.py`, `security_enhanced.py`, `partition_detection.py` ← PROCHAINE
- **Date cible** : 2026-04-11

### 1.2 Nettoyage doublons écrans + navigation.py
- **Fichiers** : `navigation.py`
- **Description** : `navigation.py` importe `graph_enhanced`, `security_enhanced`, `partition_detection`, `cross_compile_screen`, `multiarch_screen`, `moduleregistry_screen`. Ces écrans ne sont PAS dans `app.py` screen_map (qui utilise `graph.py`, `security.py`, etc.). Décider : supprimer `navigation.py` ou le mettre à jour vers les écrans canoniques.
- **Statut** : À faire (après 1.1)
- **Date cible** : 2026-04-12

### 1.3 Stub ModuleRegistry cassé
- **Fichiers** : `lib/ui/screens/module_registry.py`, `lib/function/module/registry.py`
- **Description** : `module_registry.py` importe `ModuleRegistry` qui est un stub vide. Crash au mount.
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
| 2026-04-10 | Audit partiel : `moduleregistry_screen.py` OK, `cross_compile_screen.py` corrigé. |
| 2026-04-11 | Audit complet : 3 écrans `_enhanced`/`_detection` encore cassés (bridge direct). `navigation.py` importe des écrans hors `app.py` screen_map. |
