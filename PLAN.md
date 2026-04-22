# PLAN.md — fsdeploy

> **Concept** : Orchestration de Graphe Sécurisée (Context-Aware DAG).
> **État** : Graphe et Config unifiés. Passage à l'exécution multi-mode.

---

## 🏗 Phase 1 : Système (TERMINÉ ✅)
- [x] **Bootstrap** : Cage `/opt/fsdeploy/bootstrap` opérationnelle.
- [x] **Venv** : Environnement Python isolé.

## ⚙️ Phase 2 : Le Scheduler (Moteur d'Exécution Unique)
- [ ] **Multi-Mode Runner** : Implémenter le switch Standard / Sudo / Chroot.
- [ ] **Stdin Injection** : Gérer la transmission du password via `subprocess.Popen`.
- [ ] **Cage Lifecycle** : Automatiser `mount --bind` (dev/proc/sys) -> `chroot` -> `umount`.

## 🔒 Phase 3 : Validation & UI (Le Pont)
- [ ] **Security Enforcement** : Finaliser le hook qui valide les nœuds du graphe par rapport à `defaults.ini`.
- [ ] **SudoModal** : Écran de capture de mot de passe déclenché par le Scheduler.
- [ ] **Audit Final** : Purge des appels système directs dans les 23 écrans.
