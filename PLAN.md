# PLAN.md — fsdeploy

> **Statut** : Phase de transition vers l'exécution unifiée.
> **Objectif** : Rendre le Scheduler totalement autonome via le Graphe et la Config.

---

## 🏗️ Phase 1 : Système (TERMINÉ ✅)

## ⚙️ Phase 2 : Le Runner du Scheduler (EN COURS 🚀)
- [ ] **Runtime Injector** : Moteur de formatage des commandes via `detected.ini`.
- [ ] **Cage Lifecycle** : Automatisation `mount` / `chroot` / `umount`.
- [ ] **The Multi-Runner** : Gestion des flux `Standard`, `Sudo`, `Chroot` avec injection `stdin`.

## 🔒 Phase 3 : Interface & Découplage (À VENIR)
- [ ] **SudoModal** : Intégration de la capture de secret asynchrone.
- [ ] **UI Refactor** : Migration massive des écrans vers le système d'Intentions.
- [ ] **Security Audit** : Vérification de la non-régression des garde-fous sémantiques.