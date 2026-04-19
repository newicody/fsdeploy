# PLAN.md — fsdeploy (branche `dev`)

> **Dernière mise à jour** : 2026-04-19
> **Itération worker** : 87
> **Codebase** : ~23 844 lignes Python, 67 intents, 23 écrans
> **Tâche active** : **11.1** — voir `add.md`

---

## ✅ Terminé

| ID | Description |
|----|-------------|
| — | Daemon, Scheduler, Bridge, Config, Logging, Bus, Runtime, IntentLog, Metrics, TaskGraph |
| — | 67 intents, 33 tasks réelles, launch.sh, multi-init |
| 23.1-2 | Isolation : isolation.py + cgroups intégrés executor |
| 22.1 | Fix __main__.py |
| 19.2 | 23 écrans câblés |
| 17.1 | SecurityResolver 4 niveaux + executor |
| 20.1-3, 21.1, 10.5, 9.1, 8.1, 16.x, 17.7, 7.0, Phase 1-6 | Tout le reste |

---

## 🚧 Tâche active — 11.1

Voir `add.md`.

---

## ⏳ Restant

### P1

| ID | Description |
|----|-------------|
| **11.1** | SquashFS mount + overlay setup (tasks + intents) |
| **11.2** | Câbler rootfs switch à un écran |
| **23.3** | Mount namespace pour DatasetProbeTask |

### P2

| ID | Description |
|----|-------------|
| **18.1-3** | Tests |

---

## État rootfs/overlay

| Composant | État |
|-----------|------|
| `rootfs/switch.py` (178L) | ✅ `RootfsSwitchTask`, `RootfsMountTask`, `RootfsUpdateTask` — implémentés |
| `modules/scanner/squashfs.py` | ✅ Scanner + extraction squashfs |
| `overlay_check.py` | ✅ Vérification overlayfs montés |
| Detection rôles `squashfs`, `overlay` | ✅ Dans role_patterns.py |
| **Tasks overlay standalone** | ❌ Pas de mount/setup/teardown indépendant |
| **Intents overlay** | ❌ Aucun intent `overlay.*` enregistré |