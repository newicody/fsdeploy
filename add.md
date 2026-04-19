# add.md — 23.3 : Mount namespace pour DatasetProbeTask

## Problème

`DatasetProbeTask.run()` fait `mount -t zfs ... /tmp/probe` → scan → `umount`. Si fsdeploy crash entre mount et umount, le mount reste orphelin. Avec un mount namespace, les mounts du processus fils disparaissent automatiquement.

## Fichier à modifier : `fsdeploy/lib/intents/detection_intent.py`

Modifier la classe `DatasetProbeTask` pour utiliser `multiprocessing` + `os.unshare` quand le dataset n'est pas déjà monté. Garder le code actuel comme fallback.

### Ajouter une méthode `_probe_in_namespace()` dans `DatasetProbeTask`

Ajouter **avant** la méthode `run()` existante :

```python
    def _probe_in_namespace(self, dataset, scan_path):
        """
        Probe dans un mount namespace isole.
        Le mount est auto-nettoye si le processus crash.
        Fallback sur probe direct si unshare indisponible.
        """
        import multiprocessing
        import os as _os

        # Verifier que os.unshare est disponible (Python 3.12+)
        if not hasattr(_os, 'unshare'):
            return None  # fallback

        result_queue = multiprocessing.Queue()

        def _child(dataset, scan_path_str, queue):
            try:
                import os as child_os
                from pathlib import Path
                import subprocess

                # Entrer dans un mount namespace isole
                try:
                    child_os.unshare(child_os.CLONE_NEWNS)
                except (OSError, AttributeError):
                    queue.put(None)  # fallback
                    return

                # Rendre les mounts prives
                subprocess.run(
                    ["mount", "--make-rprivate", "/"],
                    capture_output=True, timeout=5,
                )

                sp = Path(scan_path_str)
                sp.mkdir(parents=True, exist_ok=True)

                # Monter
                r = subprocess.run(
                    ["mount", "-t", "zfs", dataset, scan_path_str],
                    capture_output=True, text=True, timeout=30,
                )
                if r.returncode != 0:
                    queue.put({
                        "dataset": dataset, "role": "unknown",
                        "confidence": 0, "error": r.stderr,
                    })
                    return

                # Scanner (reimplemente ici car on est dans un fork)
                from fsdeploy.lib.function.detect.role_patterns import (
                    ROLE_PATTERNS, score_patterns,
                )
                role, confidence, details = score_patterns(sp)
                queue.put({
                    "dataset": dataset, "role": role,
                    "confidence": confidence, "details": details,
                })
                # Pas besoin de umount — le namespace meurt avec le process

            except Exception as e:
                queue.put({
                    "dataset": dataset, "role": "unknown",
                    "confidence": 0, "error": str(e),
                })

        proc = multiprocessing.Process(
            target=_child,
            args=(dataset, str(scan_path), result_queue),
        )
        proc.start()
        proc.join(timeout=60)

        if proc.is_alive():
            proc.kill()
            proc.join(timeout=5)
            return {
                "dataset": dataset, "role": "unknown",
                "confidence": 0, "error": "timeout",
            }

        try:
            return result_queue.get_nowait()
        except Exception:
            return None  # fallback
```

### Modifier la méthode `run()` existante

Remplacer le bloc `else: # Montage temporaire` par :

```python
        else:
            # Essayer avec mount namespace (anti-leak)
            scan_path = Path(tempfile.mkdtemp(prefix="fsdeploy-probe-"))
            ns_result = self._probe_in_namespace(dataset, scan_path)
            if ns_result is not None:
                try:
                    scan_path.rmdir()
                except OSError:
                    pass
                return ns_result

            # Fallback : montage direct (sans namespace)
            r = self.run_cmd(
                f"mount -t zfs {dataset} {scan_path}",
                sudo=True, check=False, timeout=30)
            if not r.success:
                try:
                    scan_path.rmdir()
                except OSError:
                    pass
                return {"dataset": dataset, "role": "unknown",
                        "confidence": 0, "error": r.stderr}
```

Le reste de `run()` (le `try/finally` avec `_scan` et `umount`) reste **inchangé** pour le fallback.

## Critères

1. `grep "unshare\|CLONE_NEWNS\|mount namespace" fsdeploy/lib/intents/detection_intent.py` → présent
2. `grep "_probe_in_namespace" fsdeploy/lib/intents/detection_intent.py` → méthode définie + appelée
3. `grep "multiprocessing" fsdeploy/lib/intents/detection_intent.py` → présent
4. Le fallback fonctionne si `os.unshare` n'est pas disponible (return None → code actuel)
5. Le code existant (scan direct, umount) reste intact comme fallback
