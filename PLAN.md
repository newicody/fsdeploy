# PLAN.md — fsdeploy

> **Architecture** : Orchestration Contextuelle via Graphe & Config.
> **État** : Moteur d'exécution (Runner/Cage) opérationnel. 

---

## 🏗️ Phase 1 : Système (TERMINÉ ✅)
- [x] **Infrastructure** : Cage et Venv isolés.

## ⚙️ Phase 2 : Le Cœur de l'Exécuteur (TERMINÉ ✅)
- [x] **Runtime Injector** : Résolution dynamique des variables.
- [x] **Multi-Tunnel Runner** : Support Standard / Sudo / Chroot.
- [x] **Cage Lifecycle** : Automatisation des montages API Kernel.

## 🔒 Phase 3 : L'Interface & Le Bridge (EN COURS 🚀)
- [ ] **SudoModal** : Créer l'écran Textual pour la capture asynchrone (non-bloquante).
- [ ] **Bridge Signals** : Remplacer les appels de fonctions par des IDs d'Intentions dans l'UI.
- [ ] **Progress Mapping** : Lier les logs de sortie du Scheduler (stdout) aux widgets Textual.
- [ ] **Audit Zero-OS** : Purge finale des imports `os` et `subprocess` dans les Screens.