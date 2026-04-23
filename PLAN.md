# PLAN.md — fsdeploy

> **Focus** : Migration de l'UI vers le système d'Intentions.
> **État** : Moteurs de calcul/exécution OK. Découplage de l'UI en cours.

---

## 🏗️ Phase 1 & 2 : Fondations (TERMINÉ ✅)
- [x] **Infrastructure** : Cage, Venv, Resolver, Scheduler.
- [x] **Runner** : Multi-tunnel (Standard/Sudo/Chroot) avec injection.

## ⚙️ Phase 3 : Migration des 23 Écrans (EN COURS 🚀)
- [ ] **Bridge Finalization** : Assurer le streaming des logs du Scheduler vers les écrans.
- [ ] **Sudo Agent** : Branchement de la modale de capture sur le flux d'exécution.
- [ ] **UI Refactor** : Purge systématique des `import subprocess` et `import os`.

## 🔒 Phase 4 : Stress Test & Livraison
- [ ] **Crash Test** : Vérifier que le `umount` lazy se déclenche bien sur interruption brutale.
- [ ] **Intent Documentation** : Finaliser le catalogue exhaustif dans `intents.ini`.