# PLAN.md — fsdeploy (branche `dev`)

> **Dernière mise à jour** : 2026-04-17 (3ème passe)
> **Tâche active** : **8.1b** — Dernier fix import path `scheduler.core.runtime`
> **Worker** : `worker.py` consomme `add.md`

---

## Conventions

ID stable · `⏳` `🚧` `✅` `⏸️` `❌` · P0-P3 · un seul `🚧` à la fois

---

## 🚧 Tâche active — 8.1b (dernière sous-tâche)

Un seul fix restant : `scheduler.py global_instance()` importe `from fsdeploy.lib.scheduler.runtime import Runtime` — le module est `fsdeploy.lib.scheduler.core.runtime`. Voir `add.md`.

---

## 📋 Phase 8 — Scheduler

| ID | Description | Prio | Statut |
|----|-------------|------|--------|
| 8.1a | `set_global_instance`, `_make_handler`, `BridgeEvent`, `poll` dual lookup | P0 | ✅ |
| 8.1b | Entry point unique (redirecteur), `pyproject.toml`, `LoggedDummyBridge` dans `ui/bridge.py`, **fix import path `scheduler.core.runtime`** | P0 | 🚧 |
| 8.2 | Réveil immédiat `event_queue.put` | P1 | ⏳ |
| 8.3 | `_process_waiting` event-driven | P2 | ⏳ |
| 8.4 | Renommer `Intent.resolve()` → `Intent.expand()` | P2 | ⏳ |

---

## 📋 Phase 9 — launch.sh

| ID | Description | Prio | Statut |
|----|-------------|------|--------|
| 9.1 | `_is_live()` retirer heuristique fstab | P0 | ⏳ |
| 9.2 | Support APT deb822 + Python `live/setup.py` | P0 | ⏳ |
| 9.3–9.11 | *(inchangé)* | P1-P2 | ⏳ |

---

## 📋 Phase 10 — UI correctifs critiques

| ID | Description | Prio | Statut |
|----|-------------|------|--------|
| 10.1–10.10 | *(inchangé — escape Unicode, imports, doublons, bindings, etc.)* | P0-P2 | ⏳ |

---

## 📋 Phase 11 — Overlay sécurisé

| ID | Description | Prio | Statut |
|----|-------------|------|--------|
| 11.1–11.6 | *(inchangé — OverlayProfile, validator, MountsScreen, multi-système)* | P0-P2 | ⏳ |

---

## 📋 Phase 12-15 — Bus, Logs, Config, UI spec

*(inchangé)*

---

## 📋 Phase 16 — Câblage lib ↔ UI

*(inchangé — 16.1-16.50)*

---

## 📋 Phase 17 — Sécurité & safety

| ID | Description | Prio | Statut |
|----|-------------|------|--------|
| 17.1 | `textual serve` auth | P0 | ⏳ |
| 17.2 | `zpool import -f` hostid check | P0 | ⏳ |
| 17.3 | Cleanup orphelins au démarrage | P0 | ⏳ |
| 17.4 | Confirmation opérations destructives | P0 | ⏳ |
| 17.5 | `sys.path` shadow stdlib | P1 | ⏳ |
| 17.6 | YouTube key leak shared_context | P1 | ⏳ |
| 17.7 | `pyproject.toml` entry point + packages | P1 | ✅ |
| 17.8 | Check ZFS dispo au démarrage | P1 | ⏳ |

---

## ✅ Historique

### 8.1a (fait 2026-04-17)

`set_global_instance`, `_make_handler` ticket propagation, `BridgeEvent`, `poll` dual lookup, `get_global_runtime` singleton.

### 8.1b — sous-tâches complétées

| Sous-tâche | Statut |
|------------|--------|
| `fsdeploy/__main__.py` argparse → redirecteur typer | ✅ |
| `pyproject.toml` entry point `fsdeploy.__main__:app` + packages `["fsdeploy"]` | ✅ |
| `ui/bridge.py` → `LoggedDummyBridge` (plus de triple fallback silencieux) | ✅ |
| `scheduler.py global_instance()` import `scheduler.runtime` → `scheduler.core.runtime` | ❌ reste |

### Phase 7 (terminée 2026-04-15) · Phases 1-6

*(inchangé)*

---

## Journal

| Date | Événement |
|------|-----------|
| 2026-04-15 | Phase 7 clôturée |
| 2026-04-17 | 8.1a fait. 8.1b : 3/4 sous-tâches faites (entry point, pyproject, LoggedDummyBridge). Reste : import path. |