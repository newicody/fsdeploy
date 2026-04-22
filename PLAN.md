# PLAN.md — fsdeploy

> **Focus** : Finalisation du moteur d'exécution et purge de l'UI.

---

## 🏗 Phase 1 : Système (TERMINÉ ✅)
- [x] **Bootstrap** : Cage `/opt/fsdeploy/bootstrap` opérationnelle.
- [x] **Venv** : Environnement Python isolé avec permissions correctes.

## ⚙️ Phase 2 : Le Scheduler (Moteur unique)
- [ ] **Runner Intégré** : Finaliser `lib/scheduler.py` pour gérer les flags `sudo` et `chroot`.
- [ ] **Bind Automator** : Script interne pour monter/démonter les API kernel de la cage.
- [ ] **Config Mapper** : Lier chaque bouton de l'UI à un bloc de ta configuration.

## 🔒 Phase 3 : UI & Refactoring Final
- [ ] **SudoModal** : Créer l'écran Textual pour la capture de mot de passe (sans stockage).
- [ ] **Bridge Refactor** : Router tous les événements vers le Scheduler.
- [ ] **Audit Écrans** : Supprimer les 23 occurrences potentielles de `os.system` / `subprocess`.