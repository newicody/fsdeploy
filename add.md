# add.md — Action 1.1 : Corriger cross_compile_screen.py

**Date** : 2026-04-10

---

## État réel après audit

| Fichier | Statut |
|---------|--------|
| `lib/ui/screens/moduleregistry_screen.py` | ✅ Déjà corrigé (property bridge, pas d'import direct) |
| `lib/ui/screens/multiarch_screen.py` | ✅ N'existe pas — `multiarch.py` est OK |
| `lib/ui/screens/cross_compile_screen.py` | ❌ **Seul fichier encore cassé** |
| `tests/.../moduleregistry_screen.py` | ❌ Import direct (copie obsolète) |
| `tests/.../crosscompile.py` | ❌ Import direct (copie obsolète) |

---

## Correction à appliquer

### 1. `lib/ui/screens/cross_compile_screen.py`

**Supprimer :**
```python
from fsdeploy.lib.scheduler.bridge import SchedulerBridge
```
```python
bridge = SchedulerBridge.default()
```

**Ajouter :**
```python
@property
def bridge(self):
    return getattr(self.app, "bridge", None)
```

### 2. `tests/fsdeploy/lib/ui/screens/moduleregistry_screen.py`

Synchroniser avec la version `lib/` (supprimer import direct, ajouter property).

### 3. `tests/fsdeploy/lib/ui/screens/crosscompile.py`

Synchroniser avec `lib/ui/screens/crosscompile.py` (qui est déjà correct).

---

## Fichiers explicites pour Aider

```
fsdeploy/lib/ui/screens/cross_compile_screen.py
```

---

## Après cette correction

Action 1.1 terminée. Prochaine : **1.2 Nettoyage doublons écrans** (unifier `_screen` vs écrans principaux, corriger `navigation.py`).
