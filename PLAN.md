# PLAN.md — fsdeploy

> **Itération** : 109 | **Config** : .aider.conf.yml active (Auto-load screens/*)
> **Objectif** : Branchement final des appels `emit`.

---

## 🚧 Tâche active — 24.1.c
- **État** : Bridge initialisé dans `on_mount` (OK).
- **Action Requise** : Remplacer `self.app.bus.emit` par `self.bridge.emit` dans TOUS les fichiers chargés.
- **Vérification** : Plus aucun appel direct au bus dans le dossier `ui/screens/`.