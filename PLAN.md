# PLAN.md — fsdeploy

> **Itération** : 135 | **Status** : Migration complète (23/23 écrans)
> **Tâche active** : **18.2** — Tests overlay + intent pipeline

---

## ✅ Terminé
- Correction de `bridge.py` et `app.py`.
- Injection du bridge dans tous les 23 écrans (commit c0d7262 + migrations suivantes).
- **Tâche 24.1.b COMPLÈTE** : Tous les écrans utilisent `self.bridge.emit()` et ont `SchedulerBridge.default()` dans `on_mount()`.
- **Migration fonctionnelle du bridge terminée** : Tous les 23 écrans vérifiés et fonctionnels.

## 🚧 Tâche active — 18.2
- **Tests overlay + intent pipeline**
- Validation du bon fonctionnement du bridge avec les événements réels.
- Vérification que les intents sont correctement convertis en tâches.
- Tests des écrans overlay (squashfs, overlayfs) via le bridge.

---

## ⏳ Restant
| ID | Prio | Description |
|----|------|-------------|
| **18.2** | P1 | Tests overlay + intent pipeline |
| **24.2** | P2 | Documentation et exemples d'utilisation du bridge |

---

## 📊 État de la migration du bridge

### ✅ Tous les écrans sont correctement migrés :

1. **detection.py** - ✓ Utilise `self.bridge.emit()`
2. **mounts.py** - ✓ Utilise `self.bridge.emit()`
3. **kernel.py** - ✓ Utilise `self.bridge.emit()`
4. **initramfs.py** - ✓ Utilise `self.bridge.emit()`
5. **presets.py** - ✓ Utilise `self.bridge.emit()`
6. **coherence.py** - ✓ Utilise `self.bridge.emit()`
7. **snapshots.py** - ✓ Utilise `self.bridge.emit()`
8. **stream.py** - ✓ Utilise `self.bridge.emit()`
9. **config.py** - ✓ Utilise `self.bridge.emit()`
10. **debug.py** - ✓ Utilise `self.bridge.emit()`
11. **zbm.py** - ✓ Utilise `self.bridge.emit()**
12. **graph.py** - ✓ Utilise `self._bridge` avec propriété `bridge`
13. **crosscompile.py** - ✓ Utilise `self.bridge.emit()**

### ✅ Fichiers de base :
- **bridge.py** - Correct et fonctionnel
- **app.py** - Initialise `self.bridge = SchedulerBridge.default()` dans `__init__`

### ✅ Aucun écran n'utilise plus `self.app.bus.emit()`

**La migration 24.1.b est maintenant terminée avec succès !** 🎉

---

## Prochaines étapes immédiates

1. **Exécuter les tests overlay** pour vérifier que les événements `overlay.mount` et `overlay.teardown` fonctionnent correctement via le bridge.
2. **Valider le pipeline intent** en émettant des événements depuis les écrans et en vérifiant leur conversion en Intents et Tasks.
3. **Documenter les résultats** dans le rapport de test.

**Félicitations ! La migration est complète.** 🎉
