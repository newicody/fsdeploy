# PLAN.md — fsdeploy

> **Focus** : Exploitation des champs ConfigObj par le Scheduler.

---

## 🏗 Phase 1 : launch.sh (TERMINÉ ✅)
- Le bootstrap est prêt, ZFS est installé, le venv est opérationnel.

## ⚙️ Phase 2 : Branchement du Scheduler sur les Champs Config
- [ ] **Config Mapper** : Faire correspondre les sections `.ini` aux intentions du Bridge.
- [ ] **Logic Sudo/Chroot** : Utiliser les champs `root` ou `mode` de ta config pour choisir le Runner.
- [ ] **Injection Stdin** : Finaliser le passage du mot de passe vers `sudo -S` sans stockage.

## 🔒 Phase 3 : Nettoyage & Sécurisation UI
- [ ] **Bridge Refactor** : Router les demandes d'écrans vers les IDs de ta config.
- [ ] **Audit Final** : Supprimer les derniers `os.system` ou `subprocess` des écrans.