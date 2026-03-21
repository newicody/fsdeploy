# Fichiers a supprimer du repo

```bash
# Doublons et stubs vides (identifiés dans FILES.md)
rm -f lib/ARCHITECTURE.py
rm -f lib/scheduler/intentlog/huffman.py
rm -f lib/scheduler/core/intent.py

# Doublon bus : garder __init__.py, supprimer init.py
rm -f lib/bus/init.py
```

# Fichiers remplaces par cette session

```bash
# executor.py et scheduler.py : remplacés (ThreadPoolExecutor non-bloquant)
# runtime.py (model) : remplacé (thread-safe)
# daemon.py : remplacé (connecte tout)
# config.py : remplacé (charge configspec externe)
```

# Nouveaux fichiers a ajouter

Voir l'arborescence complète ci-dessous.
