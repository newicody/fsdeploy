# PLAN.md — fsdeploy (branche `dev`)

> **Dernière mise à jour** : 2026-04-18
> **Itération worker** : 87
> **Codebase** : ~23 485 lignes Python, 62 intents, 23 écrans (tous câblés)
> **Tâche active** : **17.1** — voir `add.md`

---

## ✅ Terminé

| ID | Description |
|----|-------------|
| — | Daemon, Scheduler, Bridge, Config, Logging, Bus, Runtime, IntentLog, Metrics, TaskGraph |
| — | 62 intents, 34 task implementations, launch.sh, multi-init |
| 19.2 | Tous les 23 écrans câblés — 0 violation architecture |
| 20.1-3 | Scripts orphelins, double nesting, docs bridge, tests/contrib — tout nettoyé |
| 21.1 | overlay_check.py, SnapshotDestroyTask, DatasetCreateTask |
| 10.5a+b, 9.1, 8.1, 16.x, 17.7, 7.0, Phase 1-6 | Tout le reste |

---

## 🚧 Tâche active — 17.1

Voir `add.md`.

---

## ⏳ Restant

### P1

| ID | Description |
|----|-------------|
| **17.1** | SecurityResolver — niveaux explicites + intégration executor |
| **11.1** | SquashFS mount/overlay tasks |
| **11.2** | Switch rootfs à chaud |

### P2

| ID | Description |
|----|-------------|
| **18.1-3** | Tests unitaires, intégration, TUI Pilot |

---

## État sécurité actuel

- `SecurityDecorator` (DSL) : ✅ fonctionnel (`@security.dataset.snapshot`)
- `SecurityResolver.check()` : ✅ basique (role, require_root, config rules, policies)
- `SecurityResolver.resolve_locks()` : ✅ fonctionnel
- **Intégration executor** : ❌ le resolver n'est PAS appelé par l'executor avant `task.run()`
- **Niveaux nommés** : ❌ pas de `allow/deny/require_sudo/dry_run_only` explicites
- **Config [security]** : ❌ section vide dans fsdeploy.conf
- **dry_run** : ❌ pas propagé depuis la config vers les tasks