# PLAN.md — fsdeploy

> **Statut** : Architecture découplée Validée.
> **Objectif** : Synchronisation finale des flux et résilience Bare-Metal.

---

## 🏗️ Phase 1 à 3 : Architecture & Migration (TERMINÉ ✅)

## ⚙️ Phase 4 : Flux de Données et Sudo Agent (PRIORITÉ 🚀)
- [ ] **Sudo Agent Asynchrone** : Finaliser le raccordement `SudoModal` -> Bridge -> Scheduler.
- [ ] **RichLog Mapping** : Streamer les sorties `stdout` par intention pour un affichage granulaire.
- [ ] **Error Propagation** : Transformer les codes de sortie Shell en messages d'erreur UI lisibles.

## 🔒 Phase 5 : Livraison et "Zero-Scories"
- [ ] **Final Cleanup Check** : Audit des montages résiduels après fermeture brutale.
- [ ] **EOS/ZFS Final Intent Mapping** : Valider les commandes complexes dans `intents.ini`.