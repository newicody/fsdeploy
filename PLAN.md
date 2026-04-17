# PLAN.md — fsdeploy (branche `dev`)

> **Dernière mise à jour** : 2026-04-17
> **Tâche active** : **10-P0** — Doublons intents + welcome lazy + doublons écrans
> **Worker** : `worker.py` consomme `add.md`

---

## 🚧 Tâche active — 10-P0

Voir `add.md`. 4 correctifs non encore appliqués.

---

## ✅ Terminé

| ID | Description |
|----|-------------|
| 8.1a+b | Scheduler↔bridge unifié |
| 10.1 | Unicode `detection.py` |
| 10.3 | `LoggedDummyBridge` |
| 16.20+21 | Intents `mount.request` + `pool.import` |
| 16.50+51+52 | Doublons `config.snapshot`, `boot_intent`, `init_config_intent` |
| 17.7 | `pyproject.toml` |

---

## ⏳ Restant (résumé)

| Phase | P0 restants | P1+ |
|-------|-------------|-----|
| 9 launch.sh | 2 (is_live, deb822) | 9 |
| 10 UI | 3 (10.2, 10.4, 10.5) | 5 |
| 11 Overlay | 3 | 3 |
| 12-15 Bus/Logs/Config/Spec | 0 | 18 |
| 16 Câblage | 1 (16.53) | ~25 |
| 17 Sécurité | 4 (17.1-17.4) | 3 |
| **Total** | **13** | **~63** |

---

## Journal

| Date | Événement |
|------|-----------|
| 2026-04-15 | Phase 7 clôturée |
| 2026-04-17 | 8.1 complet. Intents P0 faits. Unicode+doublons nettoyés. Reste : 10.2/10.4/10.5/16.53 |