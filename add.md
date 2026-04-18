# add.md — 23.2 : Intégrer cgroups dans executor

## Quoi

L'executor doit créer un cgroup pour les tasks qui en demandent un (via le security decorator), et le nettoyer après exécution. Les tasks peuvent ensuite attacher leurs sous-processus au cgroup.

## A. Modifier `fsdeploy/lib/scheduler/core/executor.py`

Dans `_run_lifecycle()`, encadrer l'exécution avec le cgroup :

Trouver la méthode `_run_lifecycle` et la modifier. Avant `task.before_run()`, ajouter le setup cgroup. Après le finally, ajouter le cleanup.

```python
def _run_lifecycle(self, task) -> Any:
    """Execute le cycle de vie complet d'une task."""
    cgroup = None

    # Setup cgroup si demande par le decorator
    sec_opts = getattr(task.__class__, '_security_options', {})
    cg_cpu = sec_opts.get('cgroup_cpu', 0)
    cg_mem = sec_opts.get('cgroup_mem', 0)
    if cg_cpu or cg_mem:
        try:
            from fsdeploy.lib.scheduler.core.isolation import CgroupLimits
            if CgroupLimits.available():
                cgroup = CgroupLimits(
                    name=f"task-{task.id}",
                    cpu_percent=int(cg_cpu) if cg_cpu else 100,
                    mem_max_mb=int(cg_mem) if cg_mem else 0,
                )
                cgroup.create()
                task._cgroup = cgroup
        except Exception:
            pass  # cgroup optionnel, on continue sans

    try:
        # ... le reste du lifecycle existant (before_run, run, after_run) ...
        # GARDER LE CODE EXISTANT ICI
        if hasattr(task, 'before_run'):
            task.before_run()

        result = task.run()

        if hasattr(task, 'after_run'):
            task.after_run()

        return result
    finally:
        # Cleanup cgroup
        if cgroup is not None:
            try:
                cgroup.cleanup()
            except Exception:
                pass
            task._cgroup = None
```

**Important :** ne pas réécrire toute la méthode — seulement ajouter le setup cgroup avant le try et le cleanup dans le finally. Garder tout le code existant (error handling, logging, etc.) intact.

## B. Modifier `fsdeploy/lib/function/kernel/switch.py`

La classe `KernelCompileTask` est le premier use case. Ajouter l'option cgroup au decorator existant :

Trouver le decorator de `KernelCompileTask` et ajouter les options :

```python
@security.kernel.compile(require_root=True, cgroup_cpu=50, cgroup_mem=4096)
class KernelCompileTask(Task):
```

Dans la méthode `run()` de `KernelCompileTask`, si un cgroup est disponible, attacher le sous-processus :

```python
proc = subprocess.Popen(cmd, ...)
if hasattr(self, '_cgroup') and self._cgroup:
    self._cgroup.attach(proc.pid)
proc.wait()
```

## Critères

1. `grep "cgroup\|CgroupLimits" fsdeploy/lib/scheduler/core/executor.py` → présent (setup + cleanup)
2. `grep "cgroup_cpu.*50\|cgroup_mem.*4096" fsdeploy/lib/function/kernel/switch.py` → présent sur KernelCompileTask
3. Le cgroup est créé AVANT `task.run()` et nettoyé APRÈS (dans finally)
4. Si cgroups v2 non disponible, l'exécution continue normalement (pas de crash)
