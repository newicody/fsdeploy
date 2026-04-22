# PLAN.md — fsdeploy

> **Concept** : Orchestration pilotée par les métadonnées (Config-Driven).
> **État** : Infrastructure prête, passage à la logique de vol.

---

## 🏗 Phase 1 : Système (TERMINÉ ✅)
- [x] **launch.sh** : Cage d'exécution (`/opt/fsdeploy/bootstrap`) et venv isolés.

## ⚙️ Phase 2 : Scheduler (L'Exécuteur Universel)
- [ ] **Config Mapper** : Intégration de la logique de lecture des sections ConfigObj.
- [ ] **Runner Multi-Mode** :
    - Gestion du flux **User** (standard).
    - Gestion du flux **Sudo-Host** (via `sudo -S -k` et stdin).
    - Gestion du flux **Sudo-Chroot** (bind mounts + chroot).
- [ ] **Lifecycle Manager** : Automatisation du cycle `Mount Bind -> Chroot -> Unmount`.

## 🔒 Phase 3 : UI & Bridge (L'Interface Client)
- [ ] **SudoModal** : Capture asynchrone du mot de passe.
- [ ] **Event Routing** : Migration des 23 écrans vers des émissions d'IDs de config.