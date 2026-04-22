# PLAN.md — fsdeploy

> **Focus** : Pilotage du Scheduler via les champs ConfigObj.
> **Objectif** : Zéro commande en dur, tout passe par les définitions de la config.

---

## 🏗 Phase 1 : Infrastructure (TERMINÉ ✅)
- [x] **launch.sh** : Bootstrap/Cage opérationnel avec ZFS et venv.

## ⚙️ Phase 2 : Scheduler (Le Cerveau Opérationnel)
- [ ] **Config Resolver** : Mapper les intentions UI aux sections ConfigObj.
- [ ] **Execution Router** : 
    - Lire les drapeaux (`need_root`, `environment`, etc.) dans les champs.
    - Router vers `subprocess.Popen` avec injection de password si nécessaire.
- [ ] **Cage Manager** : Automatiser les `bind mounts` avant l'entrée en chroot.

## 🔒 Phase 3 : UI & Bridge (L'Interface Client)
- [ ] **SudoModal** : Intégration de la capture de pass pour le Scheduler.
- [ ] **Bridge Signals** : Remplacer les appels système des écrans par des IDs de config.