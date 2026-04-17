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

- **`test_integration_7_17.py`** importe `NavigationScreen` — supprimer cette ligne et retirer `NavigationScreen` de la liste testée.
- **`remove_duplicates.sh`** (créé par le worker précédent) — peut être supprimé aussi, il est obsolète.
- Si d'autres fichiers importent `graph_enhanced`, `security_enhanced`, ou `NavigationScreen` → supprimer ces imports.

## Critères

1. Les 3 fichiers n'existent plus
2. `grep -r "graph_enhanced\|security_enhanced\|NavigationScreen" fsdeploy/ --include="*.py"` → aucun résultat
3. `cd fsdeploy/lib && python3 test_run.py` → 3/3 pass
