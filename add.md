# add.md — Action 1.1 : Corrections écrans

**Date** : 2026-04-10

---

## Problème

3 écrans importent directement `SchedulerBridge` depuis `lib/` — violation de l'architecture :

```python
# MAUVAIS (cross_compile_screen.py, multiarch_screen.py)
from fsdeploy.lib.scheduler.bridge import SchedulerBridge
class CrossCompileScreen(Screen):
    bridge = SchedulerBridge.default()  # singleton class-level
```

Les écrans bien faits utilisent une property :

```python
# BON (stream.py)
class StreamScreen(Screen):
    @property
    def bridge(self):
        return getattr(self.app, "bridge", None)
```

---

## Correction à appliquer

Pour chaque écran fautif :

1. **Supprimer** : `from fsdeploy.lib.scheduler.bridge import SchedulerBridge`
2. **Supprimer** : `bridge = SchedulerBridge.default()` (class-level)
3. **Ajouter** property bridge :
```python
@property
def bridge(self):
    return getattr(self.app, "bridge", None)
```
4. **Garder** tous les appels `self.bridge.emit(...)` — ils fonctionnent déjà avec la property.

---

## Fichiers à modifier

| Fichier | Lignes à changer |
|---------|-----------------|
| `lib/ui/screens/cross_compile_screen.py` | Supprimer import L10 + class attr L20, ajouter property |
| `lib/ui/screens/multiarch_screen.py` | Supprimer import L10 + class attr L20, ajouter property |
| `lib/ui/screens/moduleregistry_screen.py` | Vérifier et corriger si même pattern |

---

## Après cette correction

L'action 1.1 sera terminée. Prochaine action : **#2 Mode dry-run** (`--dry-run` dans CLI + propagation dans les tâches).
