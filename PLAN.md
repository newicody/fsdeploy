# PLAN.md — fsdeploy

> **Concept** : Le Scheduler comme exécuteur exclusif des définitions ConfigObj.
> **Isolation** : Utilisation systématique du chroot pour les actions système définies.

---

## 🏗 Phase 1 : Infrastructure (TERMINÉ ✅)
- [x] **launch.sh** : Bootstrap/Cage (`/opt/fsdeploy/bootstrap`) et venv prêts.

## ⚙️ Phase 2 : Le Scheduler (Action Server)
- [ ] **Config Parser** : Charger et mapper les sections ConfigObj.
- [ ] **Execution Logic** : 
    - Identifier les modes (User, Sudo, Chroot) via les clés de config.
    - Gérer l'injection de mot de passe via `stdin` pour `sudo -S -k`.
- [ ] **Cage Orchestrator** : Gérer les montages éphémères (`bind`) requis pour le chroot.

## 🔒 Phase 3 : UI & Bridge (Client)
- [ ] **SudoModal** : Capture du mot de passe à la demande du Scheduler.
- [ ] **Intent Bridge** : Remplacer les appels directs par des envois d'IDs de section.