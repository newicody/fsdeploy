# add.md — Action 6.2 : Supprimer cross_compile_screen.py

**Date** : 2026-04-12

---

## Problème

`fsdeploy/lib/ui/screens/cross_compile_screen.py` ne contient qu'un `raise ImportError` avec un message de redirection vers `crosscompile.py`. Plus aucun fichier ne l'importe (`navigation.py` et `app.py` utilisent `crosscompile`). Ce fichier ne sert plus qu'à créer de la confusion.

---

## Action

Supprimer le fichier. `scripts/cleanup.sh` contient déjà la commande.

---

## Fichier Aider

```
fsdeploy/lib/ui/screens/cross_compile_screen.py   (supprimer)
```

---

## Après

**Phase 6 terminée. PLAN complet — aucune tâche restante.**
