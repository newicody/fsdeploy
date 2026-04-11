# add.md — Action 2.1 : Health-check (reste à faire)

**Date** : 2026-04-11

---

## État actuel

- ✅ `daemon.py` : émet `Event(name="health.check")` au démarrage
- ❌ `system_intent.py` : pas de `@register_intent("health.check")` → l'event est silencieusement ignoré
- ❌ `lib/function/health/check.py` : n'existe pas

---

## Reste à faire

### 1. Créer `lib/function/health/check.py` — `HealthCheckTask`

Vérifie :
- `which zpool` / `which zfs` (binaires présents)
- `sudo -n zpool list` (permissions sudo)
- espace disque `/` > 100 MB (`shutil.disk_usage`)
- `sys.version_info >= (3, 10)`

Retourne `{"checks": [{check, ok, message}, ...], "all_ok": bool}`

### 2. Ajouter dans `lib/intents/system_intent.py`

```python
@register_intent("health.check")
class HealthCheckIntent(Intent):
    def build_tasks(self):
        from ..function.health.check import HealthCheckTask
        return [HealthCheckTask(id="health_check", params=self.params, context=self.context)]
```

---

## Fichiers Aider

```
fsdeploy/lib/function/health/__init__.py
fsdeploy/lib/function/health/check.py
fsdeploy/lib/intents/system_intent.py
```

---

## Après

2.1 terminé. Prochaine : **2.2** (MountManager).
