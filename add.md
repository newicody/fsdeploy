# add.md — 10.5 : Supprimer 3 fichiers doublons

---

## Quoi

Supprimer 3 fichiers qui sont des doublons inutilisés :

1. **`fsdeploy/lib/ui/screens/graph_enhanced.py`** — doublon de `graph.py`. Jamais référencé dans `app.py screen_map`.
2. **`fsdeploy/lib/ui/screens/security_enhanced.py`** — doublon de `security.py`. Jamais référencé dans `app.py screen_map`.
3. **`fsdeploy/lib/ui/screens/navigation.py`** — code mort. Importe les deux fichiers ci-dessus. Pas dans `app.py screen_map`, pas de binding, inaccessible.

## Pourquoi

Ces fichiers ne sont utilisés nulle part dans l'app. `app.py screen_map` pointe vers `graph.py` (GraphScreen) et `security.py` (SecurityScreen) — les versions simples. Les versions `_enhanced` et `navigation.py` sont des prototypes jamais câblés qui créent de la confusion.

## Nettoyage des références

Après suppression, vérifier et corriger tout fichier qui les importe :

- **`tests/ui/test_screens_integration.py`** importe `GraphEnhancedScreen`, `SecurityEnhancedScreen`, et `NavigationScreen` — supprimer ces imports et retirer ces classes des tests.
- **`remove_duplicates.sh`** (si présent) — peut être supprimé aussi, il est obsolète.
- Tout autre fichier référençant `graph_enhanced`, `security_enhanced`, ou `NavigationScreen` → supprimer ces imports.

## Critères de complétion

1. Les 3 fichiers n'existent plus
2. `grep -r "graph_enhanced\|security_enhanced\|NavigationScreen" fsdeploy/ --include="*.py"` → aucun résultat
3. `grep -r "graph_enhanced\|security_enhanced\|NavigationScreen" tests/ --include="*.py"` → aucun résultat
4. `cd fsdeploy/lib && python3 -c "from fsdeploy.lib.ui.app import FsDeployApp"` → pas d'erreur d'import

---

## Prochaine tâche après 10.5

**10.2** — Audit Textual 8.x compatibilité sur tous les écrans :
- Vérifier qu'aucun écran n'assigne `self.name = "..."` dans `__init__`
- Vérifier `Select.NULL` (pas `Select.BLANK`)
- Vérifier `on_data_table_row_highlighted` (pas `on_data_table_row_selected`)
