# PLAN.md — fsdeploy

> **Stratégie** : Centralisation de l'exécution sur le Scheduler.
> **Moteur** : Exploitation des modes d'exécution définis dans la configuration ConfigObj.

---

## 🏗 Phase 1 : launch.sh (L'Installateur & Cage)
- [ ] **Élévation Privilèges** : Proposer `sudo` ou `su` pour la préparation initiale.
- [ ] **Détection Distro** : Identifier `bookworm` (Backports) ou `trixie` (Testing).
- [ ] **Cage Builder** : debootstrap de `/opt/fsdeploy/bootstrap` avec outils ZFS.
- [ ] **User venv** : Setup de l'environnement Python pour l'utilisateur courant.

## ⚙️ Phase 2 : Centralisation du Scheduler
- [ ] **Refonte du Scheduler** : Devenir l'unique exécuteur système du logiciel.
- [ ] **Exploitation Config** : Lire les flags d'exécution (sudo, chroot) directement depuis la config.
- [ ] **Modes d'Exécution** : Valider et traiter les 3 modes (Standard, Sudo-Host, Sudo-Chroot).

## 🔒 Phase 3 : Nettoyage UI & Auth
- [ ] **__main__.py** : Point d'entrée avec relance automatique dans le venv local.
- [ ] **SudoModal** : Interface de saisie de mot de passe invoquée par le Bridge.
- [ ] **Audit Écrans** : Suppression radicale de `os` et `subprocess` dans les 23 écrans.