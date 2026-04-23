# PLAN.md — fsdeploy

> **Philosophie** : Architecture Headless & Orchestration Déclarative.
> **État** : Core & Migration UI terminés. Phase de synchronisation finale.

---

## 🏗️ Phase 1, 2 & 3 : Infrastructure & Découplage (TERMINÉ ✅)

## ⚙️ Phase 4 : Synchronisation & Flux (EN COURS 🚀)
- [ ] **Sudo Agent Asynchrone** : Finaliser l'injection du secret via `SudoModal` vers le `stdin` du Runner.
- [ ] **Real-time Log Streamer** : Mapper les flux `stdout/stderr` de la cage vers les widgets RichLog.
- [ ] **State Reporting** : Afficher l'état d'avancement global du graphe (DAG) sur l'UI.

## 🔒 Phase 5 : Livraison "Bare Metal"
- [ ] **Audit de Résilience** : Vérifier que le `cleanup_cage` se déclenche sur un `SIGTERM` système.
- [ ] **Final Mapping** : S'assurer que chaque intention ZFS et EOS est 100% fonctionnelle dans le graphe.