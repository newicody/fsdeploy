# PLAN.md — fsdeploy (branche `dev`)

> **Dernière mise à jour** : 2026-04-17 (4ème passe)
> **Tâche active** : **P0-batch** — Intents manquants + Unicode + doublon
> **Worker** : `worker.py` consomme `add.md`

---

## Conventions

ID stable · `⏳` `🚧` `✅` `⏸️` `❌` · P0-P3 · un seul `🚧` à la fois

---

## 🚧 Tâche active — P0-batch (16.20 + 16.21 + 16.50 + 10.1)

Maintenant que le scheduler↔bridge est unifié (8.1 ✅), les premiers crashs visibles sont : events UI sans intent handler (tickets en pending éternel), Unicode cassé, doublon intent. Voir `add.md`.

---

## 📋 Phase 8 — Scheduler

| ID | Description | Prio | Statut |
|----|-------------|------|--------|
| 8.1a | `set_global_instance`, `_make_handler`, `BridgeEvent`, `poll` dual lookup | P0 | ✅ |
| 8.1b | Entry point unique, `pyproject.toml`, `LoggedDummyBridge`, import path fix | P0 | ✅ |
| 8.2 | Réveil immédiat `event_queue.put` | P1 | ⏳ |
| 8.3 | `_process_waiting` event-driven | P2 | ⏳ |
| 8.4 | Renommer `Intent.resolve()` → `Intent.expand()` | P2 | ⏳ |

---

## 📋 Phase 9 — launch.sh

| ID | Description | Prio | Statut |
|----|-------------|------|--------|
| 9.1 | `_is_live()` retirer heuristique fstab | P0 | ⏳ |
| 9.2 | Support APT deb822 + Python `live/setup.py` | P0 | ⏳ |
| 9.3 | `_wait_dkms()` matcher `$(uname -r)` | P1 | ⏳ |
| 9.4 | Sudoers filtrés `command -v` | P1 | ⏳ |
| 9.5 | `trap ERR` + restauration sources.list | P1 | ⏳ |
| 9.6 | Défaut `RUN_AFTER=0` | P2 | ⏳ |
| 9.7 | ACL venv `setfacl -d` | P2 | ⏳ |
| 9.8 | `--update` régénérer wrappers | P1 | ⏳ |
| 9.9 | `--update` vérifier exit pip avant `exec` | P1 | ⏳ |
| 9.10 | Vérif espace disque 512 Mo | P2 | ⏳ |
| 9.11 | Lock concurrent `flock` | P2 | ⏳ |

---

## 📋 Phase 10 — UI correctifs critiques

| ID | Description | Prio | Statut |
|----|-------------|------|--------|
| 10.1 | Escape Unicode `detection.py` `"2705"` → `"\u2705"` | P0 | 🚧 |
| 10.2 | Uniformiser imports écrans | P0 | ⏳ |
| 10.3 | `DummyBridge` log warning | P0 | ✅ |
| 10.4 | `welcome.py` imports lazy | P0 | ⏳ |
| 10.5 | Supprimer doublons écrans | P0 | ⏳ |
| 10.6 | `MultiArchScreen` bridge → `@property` | P1 | ⏳ |
| 10.7 | `ConfigSnapshotScreen` via bridge.emit | P1 | ⏳ |
| 10.8 | `NavigationScreen` enregistrer ou supprimer | P2 | ⏳ |
| 10.9 | Bindings `e/l/u/z` manquants | P1 | ⏳ |
| 10.10 | `_refresh_from_store` erreurs uniquement | P1 | ⏳ |

---

## 📋 Phase 11 — Overlay sécurisé

| ID | Description | Prio | Statut |
|----|-------------|------|--------|
| 11.1–11.6 | *(inchangé)* | P0-P2 | ⏳ |

---

## 📋 Phase 12-15

*(inchangé)*

---

## 📋 Phase 16 — Câblage lib ↔ UI

### B — Events UI sans intent

| ID | Event | Intent à créer | Prio | Statut |
|----|-------|----------------|------|--------|
| 16.20 | `mount.request` | `@register_intent("mount.request")` → `DatasetMountTask` | P0 | 🚧 |
| 16.21 | `pool.import` | `@register_intent("pool.import")` → `PoolImportTask` | P0 | 🚧 |
| 16.22–16.24 | *(inchangé)* | P1-P2 | ⏳ |

### E — Doublon

| ID | Problème | Prio | Statut |
|----|----------|------|--------|
| 16.50 | `config.snapshot.*` défini dans `system_intent.py` ET `config_intent.py` | P0 | 🚧 |

### A, C, D — *(inchangé)*

---

## 📋 Phase 17 — Sécurité & safety

| ID | Description | Prio | Statut |
|----|-------------|------|--------|
| 17.1–17.4 | *(inchangé)* | P0 | ⏳ |
| 17.5–17.6 | *(inchangé)* | P1 | ⏳ |
| 17.7 | `pyproject.toml` | P1 | ✅ |
| 17.8 | Check ZFS dispo | P1 | ⏳ |

---

## ✅ Historique

### 8.1 (terminé 2026-04-17)

| Sous-tâche | Fichiers |
|------------|----------|
| 8.1a | scheduler.py, daemon.py, bridge.py, model/event.py, model/runtime.py |
| 8.1b | fsdeploy/__main__.py (redirecteur), pyproject.toml, ui/bridge.py (LoggedDummyBridge), scheduler.py (import .core.runtime) |

### Phase 7 (terminée 2026-04-15) · Phases 1-6

*(inchangé)*

---

## Journal

| Date | Événement |
|------|-----------|
| 2026-04-15 | Phase 7 clôturée |
| 2026-04-17 | 8.1 terminé (scheduler↔bridge unifié). Prochaine : batch P0 quick fixes |