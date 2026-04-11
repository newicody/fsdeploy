# add.md — Action 1.2 : Corriger navigation.py imports

**Date** : 2026-04-11

---

## Problème

`navigation.py` importe depuis des fichiers `_screen` qui sont des doublons :

```python
from fsdeploy.lib.ui.screens.cross_compile_screen import CrossCompileScreen  # doublon
from fsdeploy.lib.ui.screens.multiarch_screen import MultiArchScreen          # n'existe pas ou doublon
```

Les écrans canoniques (utilisés par `app.py` screen_map) sont `crosscompile.py` et `multiarch.py`.

Les imports `graph_enhanced`, `security_enhanced`, `partition_detection` sont corrects — ce sont des écrans distincts (enhanced), pas des doublons.

---

## Correction

Dans `fsdeploy/lib/ui/screens/navigation.py`, remplacer :

```python
from fsdeploy.lib.ui.screens.cross_compile_screen import CrossCompileScreen
from fsdeploy.lib.ui.screens.multiarch_screen import MultiArchScreen
```

Par :

```python
from fsdeploy.lib.ui.screens.crosscompile import CrossCompileScreen
from fsdeploy.lib.ui.screens.multiarch import MultiArchScreen
```

Les 4 autres imports restent inchangés.

---

## Fichier Aider

```
fsdeploy/lib/ui/screens/navigation.py
```

---

## Après

Ajouter à CLEANUP.md :
- `fsdeploy/lib/ui/screens/cross_compile_screen.py` (doublon de `crosscompile.py`)

Prochaine action : **1.3** (stub ModuleRegistry).
