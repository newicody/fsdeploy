# PLAN.md — fsdeploy

> **Itération** : 110 | **Mode** : Full-Context (via .aider.conf.yml)
> **Objectif** : Validation de la redirection UI -> Bridge.

---

## ✅ Terminé
- Configuration automatique du contexte via YAML.
- Initialisation `on_mount` sur l'intégralité du dossier `screens/`.

## 🚧 Tâche active — 24.1.d (L'ESTOCADE)
- **Remplacement de masse** : Migrer `self.app.bus.emit` -> `self.bridge.emit` sur les écrans restants.
- **Validation unitaire** : Vérifier un écran complexe (ex: `kernel.py`) pour confirmer que le `ticket_id` est bien généré.
- **Cleanup** : Suppression des références directes au `MessageBus` dans l'UI.