add.md — Tâche 7.8 : Supprimer tests/fsdeploy/

Date : 2026-04-13
📌 Problème Identifié

Le dossier tests/fsdeploy/ est une copie partielle et obsolète du dossier fsdeploy/. Il contient 29 fichiers, dont :

    Des stubs inutiles (cross_compile_screen.py, moduleregistry_screen.py) qui re-exportent depuis des fichiers existants dans fsdeploy/lib/ui/screens/.
    Des versions désynchronisées de fichiers comme crosscompile.py (6 651 octets dans tests/fsdeploy/ vs 1 497 octets dans fsdeploy/).

Conséquences :

    Duplication inutile : Maintenance complexe et incohérences entre les deux dossiers.
    Maintenance difficile : Toute modification dans fsdeploy/ doit être répercutée dans tests/fsdeploy/.
    Risque de bugs : Les écrans qui importent depuis tests/fsdeploy/ peuvent utiliser des versions obsolètes.

📌 Tâches à Réaliser

    Supprimer le dossier entier tests/fsdeploy/ (29 fichiers).
    Vérifier que les tests passent sans ce dossier.
    Mettre à jour les imports (si nécessaire) pour utiliser fsdeploy/ directement.

📂 Fichiers Concernés
tests/fsdeploy/lib/ui/screens/cross_compile_screen.py
140 octets
Stub inutilisé (re-exporte depuis crosscompile.py).
tests/fsdeploy/lib/ui/screens/moduleregistry_screen.py
150 octets
Stub inutilisé (re-exporte depuis module_registry.py).
tests/fsdeploy/lib/ui/screens/crosscompile.py
6 651 octets
Version obsolète (plus complète que dans fsdeploy/).
tests/fsdeploy/lib/ui/screens/module_registry.py
3 666 octets
Version obsolète.
Tous les 29 fichiers du dossier tests/fsdeploy/
—
Copie obsolète et source de confusion.
🔍 Validation Après Correction

    Vérifier que tests/ ne dépend plus de tests/fsdeploy/ :
        Aucun import depuis tests.fsdeploy.* ne doit exister.
        Les tests doivent fonctionner avec la structure fsdeploy/ uniquement.

    Vérifier les imports dans les écrans :
        Remplacer les imports depuis tests.fsdeploy.lib.ui.screens.* par fsdeploy.lib.ui.screens.*.

    Exécuter les tests :

    python -m pytest tests/ -v

    → Tous les tests doivent passer.
