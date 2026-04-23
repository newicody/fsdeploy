# PLAN.md — fsdeploy

> **Statut** : Migration de l'UI complétée à 90%. Moteur d'exécution validé.
> **Objectif** : Fiabilisation du flux de données et gestion des imprévus.

---

## 🏗️ Phase 1, 2 & 3 : Infrastructure & Découplage (TERMINÉ ✅)

## ⚙️ Phase 4 : Synchronisation & Flux (EN COURS 🚀)
- [ ] **Sudo Agent Loop** : Finaliser le raccordement de l'injection du secret `stdin` via le Bridge.
- [ ] **RichLog Routing** : S'assurer que chaque écran d'action affiche son flux de logs spécifique sans mélange.
- [ ] **State Persistence** : Sauvegarder l'état du graphe pour pouvoir reprendre après une erreur mineure.

## 🔒 Phase 5 : Finalisation "Bare Metal"
- [ ] **Audit de Nettoyage** : Vérification finale des points de montage après sortie de Cage.
- [ ] **Final Intent Catalog** : Compléter les commandes pour EOS et les configurations réseau.