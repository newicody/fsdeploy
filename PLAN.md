# PLAN.md — fsdeploy

> **Concept** : Orchestration Contextuelle & Sécurisée.
> **État** : Moteurs de calcul et d'exécution OK. Passage à l'unification de l'UI.

---

## 🏗️ Phase 1 & 2 : Fondations & Moteurs (TERMINÉ ✅)
- [x] **Infrastructure** : Cage, Venv, Resolver, Scheduler.
- [x] **Runtime Engine** : Injector, Multi-Runner, Cage Lifecycle.

## ⚙️ Phase 3 : Le Grand Nettoyage de l'UI (EN COURS 🚀)
- [ ] **Bridge Finalization** : Router les événements de statut (logs, progression) vers les widgets.
- [ ] **SudoModal Integration** : Branchement final du secret vers le pipe stdin du Runner.
- [ ] **UI Purge (The 23 Screens)** : 
    - Remplacer les 23 occurrences de logique système par des `emit("INTENT")`.
    - Supprimer définitivement les imports `os` et `subprocess` des fichiers de vue.

## 🔒 Phase 4 : Audit & Livraison (À VENIR)
- [ ] **Stress Test** : Vérifier la robustesse du `umount` lors d'un crash forcé dans la cage.
- [ ] **Documentation** : Générer le catalogue des `intents.ini`.