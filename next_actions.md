# Suivi des actions prioritaires

**Date de début** : 2026-04-09
**Dernière mise à jour** : 2026-04-11

## Actions P0

### 1. BridgeScreenMixin — ✅ Terminé
### 1.1 Intégration bridge — ✅ Terminé

### 1.2 Corriger imports navigation.py ← TERMINÉ
- **Fichier** : `fsdeploy/lib/ui/screens/navigation.py`
- **Problème** : `cross_compile_screen.py` est devenu un stub `raise ImportError`. `navigation.py` l'importe encore → crash.
- **Action** : remplacer 2 imports (`cross_compile_screen` → `crosscompile`, `multiarch_screen` → `multiarch`)
- **Statut** : ✅ Terminé
- **Date cible** : 2026-04-12

### 1.3 Stub ModuleRegistry cassé
- **Fichiers** : `lib/ui/screens/module_registry.py`, `lib/function/module/registry.py`
- **Statut** : À faire

### 2. Mode dry-run — À faire
### 3. Health-check au démarrage — À faire
### 4. MountManager — À faire

## Actions P1

### 5–8 : inchangées, à faire

## Journal des décisions

| Date | Événement |
|------|-----------|
| 2026-04-09 | Priorisation initiale. |
| 2026-04-10 | Corrections bridge écrans. |
| 2026-04-11 | 1.1 terminé. 1.2 marqué à tort comme fait — `navigation.py` importe un stub qui lève ImportError. |
