# Suivi des actions prioritaires

**Date de début** : 2026-04-09
**Responsable** : équipe de développement

## Actions P0

### 1. BridgeScreenMixin
- **Fichiers** : `lib/ui/mixins.py`, tous les écrans (`detection.py`, `mounts.py`, etc.)
- **Description** : Créer un mixin fournissant `emit()` et `_refresh_from_store()` pour uniformiser la connexion au bridge.
- **Statut** : À faire
- **Date cible** : 2026-04-10

### 2. Mode dry-run
- **Fichiers** : `__main__.py` (ajouter l'option), `lib/daemon.py` (propager le flag), toutes les tâches (ajouter `dry_run`).
- **Description** : Permettre de simuler les opérations sans les exécuter réellement.
- **Statut** : À faire
- **Date cible** : 2026-04-11

### 3. Health-check au démarrage
- **Fichiers** : `lib/intents/system_intent.py` (nouvel intent HealthCheckIntent), `lib/ui/screens/welcome.py`.
- **Description** : Vérifications automatiques de l'environnement ZFS, permissions, espace disque.
- **Statut** : À faire
- **Date cible** : 2026-04-12

### 4. MountManager avec journal et cleanup
- **Fichiers** : `lib/function/mount/manager.py` (nouveau), `lib/daemon.py` (hook shutdown).
- **Description** : Journal des montages, nettoyage des orphelins, rollback automatique.
- **Statut** : À faire
- **Date cible** : 2026-04-13

## Actions P1

### 5. Notifications TUI unifiées
- **Fichiers** : `lib/ui/app.py`
- **Description** : Le bridge écoute les événements task.failed/finished et appelle app.notify().
- **Statut** : À faire
- **Date cible** : 2026-04-14

### 6. Export/import de configuration
- **Fichiers** : `lib/intents/system_intent.py`, `lib/ui/screens/presets.py`
- **Description** : Étendre les presets JSON pour inclure la configuration complète de déploiement.
- **Statut** : À faire
- **Date cible** : 2026-04-15

### 7. Mode recovery
- **Fichiers** : `__main__.py` (sous-commande --recovery), `lib/intents/system_intent.py`
- **Description** : Outil de diagnostic et réparation en cas d'échec de boot.
- **Statut** : À faire
- **Date cible** : 2026-04-16

### 8. Métriques de performance
- **Fichiers** : MetricsScreen, scheduler
- **Description** : Enregistrer durée et succès/échec, afficher statistiques.
- **Statut** : À faire
- **Date cible** : 2026-04-17

## Journal des décisions

| Date | Événement |
|------|-----------|
| 2026-04-09 | Analyse du projet et priorisation des améliorations. |
