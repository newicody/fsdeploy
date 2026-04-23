# PLAN.md — fsdeploy

> **Concept** : Framework de Déploiement Data-Driven.
> **État** : Core (Graph/Scheduler/Cage) OK. Phase de raccordement UI.

---

## 🏗️ Phase 1 & 2 : L'Infrastructure (TERMINÉ ✅)
- [x] **Système** : Cage chroot, Venv isolé.
- [x] **Moteur** : Resolver (DAG), Multi-Tunnel Scheduler, Runtime Injector.

## ⚙️ Phase 3 : Raccordement & Nettoyage (EN COURS 🚀)
- [ ] **Real-time Bridge** : Connecter le flux `stdout` du Scheduler vers les widgets `RichLog` de Textual.
- [ ] **Sudo Agent Flow** : Finaliser la boucle `Scheduler -> Need Pass -> Bridge -> UI -> Scheduler`.
- [ ] **UI Migration** : Transformer les écrans système en simples émetteurs d'Intentions.

## 🔒 Phase 4 : Validation Industrielle
- [ ] **Atomic Audit** : Prouver qu'un crash UI pendant un `chroot` ne laisse aucun montage `/dev` actif.
- [ ] **Security Matrix** : Tester les limites du Hook face à des entrées malveillantes.