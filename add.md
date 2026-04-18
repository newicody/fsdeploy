# add.md — 20.1 : Nettoyage racine + double nesting

## A. Supprimer 6 scripts racine orphelins

Ces fichiers sont des scripts de maintenance ponctuels, tous obsolètes :

1. `check_imports_7.8.py` (42L) — vérification imports pour tâche 7.8, terminée
2. `cleanup_contrib.sh` (46L) — script de nettoyage contrib, exécuté
3. `cleanup_lib_ui.sh` (21L) — script de nettoyage UI, exécuté
4. `remove_tests_fsdeploy.py` (25L) — suppression tests, exécuté
5. `test_all.py` (26L) — lanceur de tests ad-hoc, remplacé par pytest
6. `test_integration_7_17.py` (89L) — test intégration tâche 7.17, terminée

Ne pas supprimer `worker.py` (pipeline de développement actif) ni `STATE.json`.

## B. Résoudre double nesting `fsdeploy/fsdeploy/`

Le dossier `fsdeploy/fsdeploy/` contient `__init__.py` et `__main__.py` qui dupliquent `fsdeploy/__init__.py` et `fsdeploy/__main__.py`. Ce sous-dossier n'est importé nulle part.

1. Vérifier : `grep -r "fsdeploy.fsdeploy" --include="*.py" .` → doit être vide
2. Si vide, supprimer `fsdeploy/fsdeploy/` entièrement

## Critères

1. Les 6 fichiers racine n'existent plus
2. `fsdeploy/fsdeploy/` n'existe plus
3. `worker.py` et `STATE.json` toujours présents
4. `python3 -c "import fsdeploy"` fonctionne toujours
