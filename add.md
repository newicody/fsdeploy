# add.md — 10.5b : Nettoyage écrans orphelins + fix Textual 8.x

---

## Quoi

3 actions groupées, toutes P0 :

### A. Nettoyer `fsdeploy/tests/ui/test_screens_integration.py`

10.5a a supprimé `graph_enhanced.py`, `security_enhanced.py`, `navigation.py` mais le fichier test les importe encore → crash import.

- Supprimer l'import `from fsdeploy.lib.ui.screens.graph_enhanced import GraphEnhancedScreen`
- Supprimer l'import `from fsdeploy.lib.ui.screens.security_enhanced import SecurityEnhancedScreen`
- Supprimer l'import `from fsdeploy.lib.ui.screens.partition_detection import PartitionDetectionScreen` (fichier supprimé en C)
- Supprimer les fonctions `test_graph_screen()`, `test_security_screen_load_rules()`, `test_partition_screen_scan()`
- Garder les 3 tests restants (`test_crosscompile_screen`, `test_multiarch_screen`, `test_moduleregistry_screen`)

### B. Fix Textual 8.x dans `fsdeploy/lib/ui/screens/history.py`

Ligne 63 : `on_data_table_row_selected` → `on_data_table_row_highlighted`
Même ligne : `DataTable.RowSelected` → `DataTable.RowHighlighted`

### C. Supprimer 5 fichiers orphelins

Aucun n'est référencé dans `app.py screen_map` :

1. `fsdeploy/lib/ui/screens/multiarch_screen.py` (93L) — doublon de `multiarch.py`
2. `fsdeploy/lib/ui/screens/livegraph.py` (143L) — pas dans screen_map
3. `fsdeploy/lib/ui/screens/partition_detection.py` (113L) — pas dans screen_map, utilise `on_data_table_row_selected`
4. `fsdeploy/ui/screens/__init__.py` (95L) — ancien emplacement hors `lib/`
5. `fsdeploy/ui/screens/graph.py` (403L) — vieille version hors `lib/`

Après suppression, supprimer le dossier `fsdeploy/ui/screens/` (et `fsdeploy/ui/` s'il est vide).

---

## Critères

1. `grep -r "graph_enhanced\|security_enhanced\|NavigationScreen" --include="*.py" .` → aucun résultat
2. `grep -rn "on_data_table_row_selected" fsdeploy/lib/ --include="*.py"` → uniquement des commentaires (compat.py, snapshots.py docstring)
3. Les 5 fichiers orphelins n'existent plus
4. `fsdeploy/ui/screens/` n'existe plus
5. Les 3 tests restants dans `test_screens_integration.py` importent correctement

---

## Prochaine tâche après 10.5b

**9.1** — `fsdeploy/lib/function/live/setup.py` : remplacer `linux-headers-amd64` hardcodé par détection dynamique via `uname -r`.
