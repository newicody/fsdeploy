# Améliorations apportées

## 2026-04-10 : BridgeScreenMixin

- Création du fichier `lib/ui/mixins.py` contenant la classe `BridgeScreenMixin`.
- Le mixin fournit les méthodes `emit(event, **params)` et `_refresh_from_store(store_key)`.
- Méthode auxiliaire `set_bridge(bridge)` pour l'injection de dépendance.
- Cette étape permet d'uniformiser la connexion au bridge pour tous les écrans.
- **Statut** : Terminé

Prochaine étape : modifier chaque écran (detection.py, mounts.py, …) pour hériter du mixin et utiliser self.bridge.
