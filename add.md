# add.md — Action 2.2 : MountManager avec journal et cleanup

**Date** : 2026-04-11

---

## Problème

Les montages ZFS sont gérés directement par les tasks individuelles (`MountDatasetTask`, `MountsScreen` callbacks). Aucun journal centralisé → pas de cleanup des montages orphelins au shutdown, pas de rollback en cas d'erreur.

---

## Objectif

Créer un `MountManager` centralisé qui :
1. **Journalise** chaque mount/umount (dataset, mountpoint, timestamp)
2. **Nettoie** les orphelins au shutdown du daemon
3. **Rollback** : démonte dans l'ordre inverse en cas d'échec d'une séquence

---

## Fichiers à créer/modifier

### 1. `lib/function/mount/manager.py` (nouveau)

```python
class MountManager:
    def __init__(self):
        self._journal: list[dict] = []  # {dataset, mountpoint, timestamp, action}
        self._lock = threading.Lock()

    def mount(self, dataset, mountpoint, task) -> bool:
        """Monte via task.run_cmd, journalise."""

    def umount(self, dataset, task) -> bool:
        """Démonte, journalise."""

    def cleanup(self, task=None):
        """Démonte tous les montages journalisés (ordre inverse)."""

    @property
    def journal(self) -> list[dict]:
        """Copie thread-safe du journal."""
```

### 2. `lib/daemon.py` — instancier et injecter

Dans `run()`, créer `MountManager()` et l'ajouter au `shared_context` pour que les tasks puissent y accéder via `self.context["mount_manager"]`. Hook `stop()` pour appeler `cleanup()`.

---

## Fichiers Aider

```
fsdeploy/lib/function/mount/__init__.py
fsdeploy/lib/function/mount/manager.py
fsdeploy/lib/daemon.py
```

---

## Après

2.2 terminé. Prochaine : **2.3** (notifications TUI unifiées).
