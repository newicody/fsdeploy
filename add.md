# add.md — Batch P0 : 16.20 + 16.21 + 16.50 + 10.1

> **Worker** : 4 correctifs indépendants. Chacun est petit. L'ensemble rend l'UI fonctionnelle.

---

## Contexte

Le scheduler↔bridge est unifié (8.1 ✅). Mais quand on clique sur un bouton dans la TUI, deux choses se passent :
- MountsScreen émet `mount.request` → aucun intent enregistré → ticket en pending éternel
- DetectionScreen émet `pool.import` → aucun intent → idem
- `detection.py` affiche `2705` au lieu de ✅

Ces 4 fixes rendent la boucle scheduler visible de bout en bout.

---

## Fix 1 — 16.20 : Intent `mount.request` manquant

### Fichier à modifier : `fsdeploy/lib/intents/detection_intent.py`

MountsScreen fait `bridge.emit("mount.request", dataset="...", mountpoint="...")`. Il n'existe aucun `@register_intent("mount.request")`.

**Ajouter** à la fin du fichier (ou dans un nouveau `mount_intent.py` importé par `intents/__init__.py`) :

```python
@register_intent("mount.request")
class MountRequestIntent(Intent):
    """Event: mount.request -> DatasetMountTask"""
    def build_tasks(self):
        from function.mount.manager import DatasetMountTask
        return [DatasetMountTask(
            id="mount_request",
            params=self.params,
            context=self.context,
        )]
```

**Note** : si `DatasetMountTask` n'existe pas dans `function/mount/manager.py`, utiliser le `MountVerifyTask` existant ou créer un intent léger qui appelle `run_cmd("mount -t zfs {dataset} {mountpoint}")` directement. L'important est que l'event ait un handler.

Vérifier aussi que `mount.verify` et `mount.umount` ont des intents — ils sont documentés dans `api_reference.md` mais doivent être vérifiés dans le code.

---

## Fix 2 — 16.21 : Intent `pool.import` manquant

### Fichier à modifier : `fsdeploy/lib/intents/detection_intent.py`

DetectionScreen fait `bridge.emit("pool.import", pool="nom_pool")` pour importer un seul pool. Seul `pool.import_all` existe.

**Ajouter** :

```python
@register_intent("pool.import")
class PoolImportIntent(Intent):
    """Event: pool.import -> importe un seul pool par nom."""
    def build_tasks(self):
        pool_name = self.params.get("pool", "")
        if not pool_name:
            return []

        class PoolImportSingleTask(Task):
            def run(self_task):
                r = self_task.run_cmd(
                    f"zpool import -f -N -o cachefile=none {pool_name}",
                    sudo=True, check=False, timeout=30,
                )
                return {
                    "pool": pool_name,
                    "success": r.success,
                    "error": r.stderr if not r.success else "",
                }

        return [PoolImportSingleTask(
            id=f"pool_import_{pool_name}",
            params=self.params,
            context=self.context,
        )]
```

**Alternative plus propre** : si `PoolImportAllTask` sait importer un seul pool via un param, réutiliser cette task avec `params={"pool": pool_name}`.

---

## Fix 3 — 16.50 : Doublon `config.snapshot.*`

### Fichiers concernés :
- `fsdeploy/lib/intents/system_intent.py` — définit `config.snapshot.save`, `config.snapshot.restore`, `config.snapshot.list`
- `fsdeploy/lib/intents/config_intent.py` — définit les **mêmes** trois intents

Le dernier importé par `intents/__init__.py` écrase le premier dans `INTENT_REGISTRY`. Résultat imprévisible.

**Fix** : supprimer les trois `@register_intent("config.snapshot.*")` de **`config_intent.py`** (garder ceux de `system_intent.py` qui sont le canonical). 

Si `config_intent.py` ne contient plus rien après suppression, supprimer le fichier et retirer l'import dans `intents/__init__.py` :
```python
# Supprimer :
try:
    from intents.config_intent import *
except ImportError:
    pass
```

---

## Fix 4 — 10.1 : Escape Unicode dans `detection.py`

### Fichier : `fsdeploy/lib/ui/screens/detection.py`

Lignes actuelles (en haut du fichier) :
```python
CHECK = "[OK]" if IS_FB else "2705"
CROSS = "[!!]" if IS_FB else "274c"
WARN  = "[??]" if IS_FB else "26a0Fe0f"
ARROW = "->" if IS_FB else "2192"
```

Affiche littéralement `2705` dans la TUI au lieu de ✅.

**Fix** :
```python
CHECK = "[OK]" if IS_FB else "\u2705"
CROSS = "[!!]" if IS_FB else "\u274c"
WARN  = "[??]" if IS_FB else "\u26a0\ufe0f"
ARROW = "->" if IS_FB else "\u2192"
```

Ou plus simple, utiliser les littéraux directement :
```python
CHECK = "[OK]" if IS_FB else "✅"
CROSS = "[!!]" if IS_FB else "❌"
WARN  = "[??]" if IS_FB else "⚠️"
ARROW = "->" if IS_FB else "→"
```

(Le fichier a le header `# -*- coding: utf-8 -*-` donc les littéraux UTF-8 sont safe. MAIS attention : le projet utilise la convention "pure ASCII content, Unicode via escape sequences" pour éviter les problèmes `textual serve`. Préférer `\uXXXX`.)

---

## Critères d'acceptation

1. **16.20** : `bridge.emit("mount.request", dataset="test", mountpoint="/mnt/test")` → le ticket passe en `completed` ou `failed` (plus de pending éternel)

2. **16.21** : `bridge.emit("pool.import", pool="test_pool")` → idem

3. **16.50** : `python3 -c "from scheduler.core.registry import INTENT_REGISTRY; print('config.snapshot.save' in INTENT_REGISTRY)"` → `True`, et un seul handler (pas deux)

4. **10.1** : lancer la TUI → DetectionScreen affiche ✅ / ❌ / ⚠️ au lieu de `2705` / `274c` / `26a0Fe0f`

5. **Tests existants** : `cd lib && python3 test_run.py` → 3/3 pass

---

## Après ce batch

Prochaines priorités :
1. **10.2 + 10.4 + 10.5** — imports uniformes, welcome.py lazy, doublons écrans
2. **11.1-11.3** — overlay sécurisé (OverlayProfile + MountsScreen)
3. **17.1-17.4** — sécurité (auth web, hostid, cleanup, confirmation)
