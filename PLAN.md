# PLAN.md — fsdeploy

> **Concept** : Framework de Déploiement Data-Driven.
> **État** : Core & Migration UI terminés. Phase de synchronisation finale.

---

## 🏗️ Phase 1 à 3 : Architecture & Purge UI (TERMINÉ ✅)

## ⚙️ Phase 4 : Flux de Données & Sudo Agent (EN COURS 🚀)
- [ ] **Sudo Agent Loop** : Finaliser l'injection `stdin` du secret via le Bridge vers la Cage.
- [ ] **RichLog Mapping** : Streamer les sorties `stdout` par intention pour un affichage granulaire.
- [ ] **State Reporting** : Affichage de la progression globale du Graphe (DAG) sur l'UI.

## 🔒 Phase 5 : Livraison "Bare Metal"
- [ ] **Audit de Résilience** : Vérifier le `cleanup_cage` sur les signaux `SIGINT/SIGTERM`.
- [ ] **Final Intent Mapping** : Valider les commandes EOS/ZFS dans `intents.ini`.