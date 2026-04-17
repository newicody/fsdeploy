# PLAN.md — fsdeploy (branche `dev`)

> **Dernière mise à jour** : 2026-04-17
> **Tâche active** : **P0-fix** — cli.py import cassé + welcome.py lazy
> **Worker** : `worker.py` consomme `add.md`

---

## 🚧 Tâche active — P0-fix

Voir `add.md`. 2 correctifs.

---

## ✅ Terminé

| ID | Description |
|----|-------------|
| 8.1a+b | Scheduler↔bridge unifié |
| 10.1 | Unicode `detection.py` |
| 10.3 | `LoggedDummyBridge` |
| 16.20+21 | Intents `mount.request` + `pool.import` |
| 16.50+51+52 | Doublons `config.snapshot`, `boot_intent`, `init_config_intent` |
| 16.53 | Doublon `init.detect` supprimé de `system_intent.py` |
| 17.7 | `pyproject.toml` |

---

## ⏳ Restant (résumé)

| Phase | P0 restants | P1+ |
|-------|-------------|-----|
| 9 launch.sh | 2 | 9 |
| 10 UI | 3 (10.2, 10.4, 10.5) | 5 |
| 11 Overlay | 3 | 3 |
| 12-15 Bus/Logs/Config/Spec | 0 | 18 |
| 16 Câblage | 1 (cli.py cassé) | ~25 |
| 17 Sécurité | 4 | 3 |
| **Total** | **13** | **~63** |

---

## Journal

| Date | Événement |
|------|-----------|
| 2026-04-15 | Phase 7 clôturée |
| 2026-04-17 | 8.1 complet. Intents+doublons nettoyés. 16.53 fait mais `cli.py` import cassé. 10.4 pas fait. |