# PLAN.md — fsdeploy

> **Concept** : Orchestration de Graphe Contextuelle & Sécurisée.
> **État** : Moteurs de calcul et d'exécution OK. Passage à l'interface asynchrone.

---

## 🏗️ Phase 1 : Système (TERMINÉ ✅)
- [x] **Infrastructure** : Cage et Venv isolés.

## ⚙️ Phase 2 : Le Cœur de l'Exécuteur (TERMINÉ ✅)
- [x] **Runtime Injector** : Résolution tardive des variables.
- [x] **Multi-Tunnel Runner** : Support Standard / Sudo / Chroot.
- [x] **Cage Lifecycle** : Automatisation des montages API Kernel.

## 🔒 Phase 3 : L'Interface & Le Bridge (EN COURS 🚀)
- [ ] **SudoModal** : Écran de capture asynchrone du secret (sans stockage RAM permanent).
- [ ] **Bridge Signals** : Routage des intentions UI vers le Resolver.
- [ ] **Log Streamer** : Branchement des sorties `stdout` du Scheduler sur les widgets UI.
- [ ] **Le Grand Nettoyage** : Purge finale des imports `os` et `subprocess` dans les 23 écrans.