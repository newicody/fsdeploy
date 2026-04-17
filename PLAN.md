# PLAN.md — fsdeploy (branche `dev`)

> **Dernière mise à jour** : 2026-04-17
> **Tâche active** : **P0-cleanup** — 10.1 + 16.51 + 16.52
> **Worker** : `worker.py` consomme `add.md`

---

## 🚧 Tâche active — P0-cleanup (10.1 + 16.51 + 16.52)

Trois correctifs restants. Voir `add.md`.

---

## ✅ Terminé

| ID | Description |
|----|-------------|
| 8.1a | `set_global_instance`, `_make_handler`, `BridgeEvent`, `poll` dual lookup |
| 8.1b | Entry point unique, `pyproject.toml`, `LoggedDummyBridge`, import `.core.runtime` |
| 10.3 | `DummyBridge` log warning |
| 16.20 | `mount.request` intent créé |
| 16.21 | `pool.import` intent créé |
| 16.50 | `config.snapshot.*` doublon nettoyé |
| 17.7 | `pyproject.toml` entry point + packages |

---

## 📋 Phase 8 — Scheduler

| ID | Description | Prio | Statut |
|----|-------------|------|--------|
| 8.2 | Réveil immédiat `event_queue.put` | P1 | ⏳ |
| 8.3 | `_process_waiting` event-driven | P2 | ⏳ |
| 8.4 | Renommer `Intent.resolve()` → `Intent.expand()` | P2 | ⏳ |

---

## 📋 Phase 9 — launch.sh

| ID | Description | Prio | Statut |
|----|-------------|------|--------|
| 9.1 | `_is_live()` retirer heuristique fstab | P0 | ⏳ |
| 9.2 | Support APT deb822 | P0 | ⏳ |
| 9.3–9.11 | dkms, sudoers, trap, ACL, update, espace, lock | P1-P2 | ⏳ |

---

## 📋 Phase 10 — UI correctifs

| ID | Description | Prio | Statut |
|----|-------------|------|--------|
| 10.1 | Unicode `detection.py` `"2705"` → `"\u2705"` | P0 | 🚧 |
| 10.2 | Uniformiser imports écrans | P0 | ⏳ |
| 10.4 | `welcome.py` imports lazy | P0 | ⏳ |
| 10.5 | Supprimer doublons écrans | P0 | ⏳ |
| 10.6–10.10 | *(inchangé)* | P1-P2 | ⏳ |

---

## 📋 Phase 11 — Overlay sécurisé · ⏳

## 📋 Phase 12-15 — Bus, Logs, Config, UI spec · ⏳

---

## 📋 Phase 16 — Câblage lib ↔ UI

| ID | Description | Prio | Statut |
|----|-------------|------|--------|
| 16.51 | `boot_intent.py` = copie identique de `detection_intent.py` — dédoublonner | P0 | 🚧 |
| 16.52 | `init.config.detect` défini dans `init_intent.py` ET `init_config_intent.py` | P0 | 🚧 |
| 16.1–16.44 | *(câblage restant)* | P1-P2 | ⏳ |

---

## 📋 Phase 17 — Sécurité · ⏳ (17.1-17.4 P0, 17.5-17.8 P1)

---

## Journal

| Date | Événement |
|------|-----------|
| 2026-04-15 | Phase 7 clôturée |
| 2026-04-17 | 8.1 complet, 16.20+16.21+16.50 faits. Reste : 10.1, 16.51, 16.52 |