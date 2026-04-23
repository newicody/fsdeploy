# PLAN.md — fsdeploy

> **Statut** : Architecture découplée et validée.
> **Objectif** : Zéro "freeze" de l'UI et résilience aux erreurs critiques.

---

## 🏗️ Phase 1, 2 & 3 : Infrastructure & Migration (TERMINÉ ✅)

## ⚙️ Phase 4 : Résilience & Flux (EN COURS 🚀)
- [ ] **Sudo Agent Loop** : Finaliser l'injection asynchrone du secret (UI -> Bridge -> Scheduler).
- [ ] **RichLog Routing** : Mapper proprement chaque sortie de commande (`stdout/stderr`) vers les widgets de logs.
- [ ] **Exception Handling** : Capturer les erreurs de la Cage pour les transformer en modales explicatives dans l'UI.

## 🔒 Phase 5 : Pré-Livraison
- [ ] **Cleanup Audit** : Vérifier la robustesse des démontages lors d'un `SIGKILL`.
- [ ] **Intent Catalog** : Finaliser les définitions ZFS et EOS dans `intents.ini`.