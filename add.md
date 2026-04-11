# add.md — Action 2.1 : Health-check au démarrage

**Date** : 2026-04-11

---

## Objectif

Au démarrage du daemon, émettre automatiquement un événement `health.check` qui vérifie les prérequis critiques. Le `WelcomeScreen` affiche le résultat.

---

## Ce qui existe déjà

- `coherence.check` : vérification complète (pools, datasets, montages) — trop lourd pour le startup
- `init.detect` : détection du système d'init
- `WelcomeScreen` : affiche infos hardware/mode mais pas de statut health

---

## Correction

### 1. `lib/intents/system_intent.py` — ajouter `HealthCheckIntent`

```python
@register_intent("health.check")
class HealthCheckIntent(Intent):
    def build_tasks(self):
        return [HealthCheckTask(id="health_check", params=self.params, context=self.context)]
```

`HealthCheckTask` (dans `lib/function/health/check.py`) vérifie :
- `zpool` et `zfs` disponibles (binaire + module noyau)
- `sudo -n zpool list` fonctionne (permissions)
- espace disque `/` > 100 MB
- Python version >= 3.10

Retourne une liste de `{check, ok, message}`.

### 2. `lib/daemon.py` — émettre `health.check` au démarrage

Dans `run()`, après `_register_all_intents()`, ajouter :
```python
self._runtime.event_queue.put(Event(name="health.check", params={}))
```

### 3. `lib/ui/screens/welcome.py` — afficher les résultats

Dans `_refresh_from_store()`, lire les résultats du health-check depuis le store et mettre à jour l'affichage.

---

## Fichiers Aider

```
fsdeploy/lib/function/health/__init__.py
fsdeploy/lib/function/health/check.py
fsdeploy/lib/intents/system_intent.py
fsdeploy/lib/daemon.py
```

---

## Après

2.1 terminé. Prochaine : **2.2** (MountManager).
