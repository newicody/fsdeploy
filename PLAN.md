# PLAN.md — fsdeploy (Adaptation & Sécurité Contextuelle)

> **Focus** : Raffinement du Resolver et synchronisation avec le Scheduler.

---

## 🏗 Phase 1 : Système (TERMINÉ ✅)

## ⚙️ Phase 2 : Raffinement du Resolver (Graphe & Sécurité)
- [ ] **Dynamic Interpolation** : Adapter le Resolver pour injecter les variables de `detected.ini` au dernier moment dans les nœuds du Graphe.
- [ ] **Security Hook Refactor** : Transformer le hook existant en validateur contextuel (croisement Intentions / Politiques / Faits).
- [ ] **Unified Scheduler Bridge** : Connecter la sortie du Resolver au Scheduler multi-mode (Sudo/Chroot).

## 🔒 Phase 3 : Orchestration & UI
- [ ] **Sudo Agent** : Gestion de la persistance éphémère du mot de passe pour une chaîne de tâches.
- [ ] **Progress Mapping** : Lier les nœuds du graphe aux barres de progression de l'UI.