# PLAN.md — fsdeploy (branche `dev`)

> **Dernière mise à jour** : 2026-04-19
> **Itération worker** : 87
> **Codebase** : ~24 300 lignes Python, 71 intents, 23 écrans
> **Tâche active** : **22.3** — voir `add.md`

---

## ✅ Terminé

| ID | Description |
|----|-------------|
| 22.2 (partiel) | `__main__.py` corrigé (parent + lib/ dans sys.path) |
| 18.1 | Tests SecurityResolver + Isolation (19 tests) |
| 11.1-2 | SquashFS/overlay tasks + intents + UI mounts |
| 23.1-2 | Isolation + cgroups executor |
| 19.2 | 23 écrans câblés |
| 17.1 | SecurityResolver 4 niveaux + executor |
| Tout le reste | 20.1-3, 21.1, 10.5, 9.1, 8.1, 16.x, 17.7, 7.0, Phase 1-6 |

---

## 🚧 Tâche active — 22.3

Voir `add.md`.

---

## P0 — CLI toujours cassée

`fsdeploy/__init__.py` = 3 lignes avec docstring non fermée → `SyntaxError` à l'import. Le commit `28e6d75` a tronqué le fichier au lieu de le corriger.

---

## ⏳ Restant après 22.3

| ID | Prio | Description |
|----|------|-------------|
| 23.3 | P1 | Mount namespace pour DatasetProbeTask |
| 18.2 | P1 | Tests overlay + intent pipeline |
| 18.3 | P2 | Tests TUI Pilot |