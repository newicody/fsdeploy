# PLAN.md — fsdeploy

> **Philosophie** : Architecture Découplée & Exécution en Cage.
> **État** : Migration UI Terminée. Core Stable.

---

## 🏗️ Phase 1, 2 & 3 : Infrastructure & Migration (TERMINÉ ✅)

## ⚙️ Phase 4 : Raccordement Final (EN COURS 🚀)
- [ ] **Sudo Agent Loop** : Finaliser l'injection du secret asynchrone via le Bridge.
- [ ] **RichLog Mapping** : Streamer le flux `stdout` du Scheduler vers les widgets UI.
- [ ] **Signal Management** : Garantir le `cleanup_cage` sur tous les signaux d'arrêt (SIGINT/SIGTERM).

## 🔒 Phase 5 : Livraison & Audit
- [ ] **Validation ZFS/EOS** : Test de bout en bout du graphe d'intentions.
- [ ] **Zero-Scorie Check** : Vérifier l'absence totale de montages résiduels après sortie.
