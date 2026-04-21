# PLAN.md — fsdeploy

> **Objectif** : Fiabilisation du lancement et gestion des retours (Full Loop).

## 🚧 En cours — 24.2.a (Audit & Launch)
- **launch.sh** : Sécurisation du démarrage (Kill process, PYTHONPATH).
- **bridge.py** : Ajout de la gestion des `_callbacks` par `ticket_id`.

## 🚧 En cours — 24.2.b (Screens Callbacks)
- **Screens** : Ajout de la logique de réception des messages du Bridge.
- **Validation** : Vérifier que l'UI réagit quand le scheduler confirme la fin d'une tâche.