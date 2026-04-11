# add.md — Action 1.1 suite : Corriger 3 écrans enhanced/detection

**Date** : 2026-04-11

---

## Problème

3 écrans ont encore l'import direct `SchedulerBridge` + attribut de classe `bridge = SchedulerBridge.default()` :

| Fichier | Lignes à corriger |
|---------|-------------------|
| `fsdeploy/lib/ui/screens/graph_enhanced.py` | `from fsdeploy.lib.scheduler.bridge import SchedulerBridge` + `bridge = SchedulerBridge.default()` |
| `fsdeploy/lib/ui/screens/security_enhanced.py` | idem |
| `fsdeploy/lib/ui/screens/partition_detection.py` | idem |

---

## Correction identique pour chaque fichier

1. **Supprimer** : `from fsdeploy.lib.scheduler.bridge import SchedulerBridge`
2. **Supprimer** : `bridge = SchedulerBridge.default()`
3. **Ajouter** dans la classe :
```python
@property
def bridge(self):
    return getattr(self.app, "bridge", None)
```

---

## Fichiers Aider

```
fsdeploy/lib/ui/screens/graph_enhanced.py
fsdeploy/lib/ui/screens/security_enhanced.py
fsdeploy/lib/ui/screens/partition_detection.py
```

---

## Contexte

Ces écrans sont importés par `navigation.py` mais ne sont PAS dans `app.py` screen_map. Ils constituent un second jeu d'écrans "enhanced" utilisés uniquement par `NavigationScreen`. L'action 1.2 traitera cette dualité — pour l'instant on corrige juste la violation bridge.

---

## Après cette correction

Action 1.1 terminée pour tous les fichiers `lib/`. Prochaine : **1.2** (décider du sort de `navigation.py` et des écrans `_enhanced`).
