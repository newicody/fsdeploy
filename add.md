# add.md — Nettoyage final (priorité basse)

**Date** : 2026-04-12

---

## PLAN terminé — reste du nettoyage

### 1. Synchroniser `tests/` avec `lib/`

Fichiers dans `tests/fsdeploy/lib/ui/screens/` qui ont encore des imports cassés :
- `cross_compile_screen.py` → import direct `SchedulerBridge`
- `multiarch_screen.py` → import direct `SchedulerBridge`
- `moduleregistry_screen.py` → import direct `SchedulerBridge`
- `partition_detection.py` → import direct `SchedulerBridge`
- `security_enhanced.py` → import direct `SchedulerBridge`
- `navigation.py` → imports `_screen` obsolètes

### 2. Supprimer fichiers obsolètes (CLEANUP.md)

- `fsdeploy/lib/ui/screens/cross_compile_screen.py` (stub `raise ImportError`)
- Vérifier les entrées de `CLEANUP.md` existant

### 3. Corriger `test_screens_integration.py`

Remplacer les imports `_screen` par les écrans canoniques pour que les tests passent.

---

## Fichiers Aider

```
tests/fsdeploy/lib/ui/screens/navigation.py
tests/fsdeploy/tests/ui/test_screens_integration.py
```
