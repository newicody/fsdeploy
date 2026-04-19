# add.md — 11.1 : SquashFS mount + overlay setup

## A. Créer `fsdeploy/lib/function/rootfs/overlay.py`

3 tasks standalone pour gérer le cycle de vie overlayfs :

```python
# -*- coding: utf-8 -*-
"""
fsdeploy.function.rootfs.overlay
==================================
Montage SquashFS + setup overlayfs.

Stack overlayfs :
    merged (target)  <-- le systeme voit ca
      |-- upper      <-- couche ecriture (tmpfs ou dataset ZFS)
      |-- work       <-- workdir overlayfs (meme fs que upper)
      +-- lower      <-- squashfs readonly

Usage :
    1. SquashfsMountTask : monte le .sfs en readonly
    2. OverlaySetupTask : cree le stack overlay complet
    3. OverlayTeardownTask : demonte tout proprement
"""

import os
from pathlib import Path
from typing import Any

from fsdeploy.lib.scheduler.model.task import Task
from fsdeploy.lib.scheduler.model.lock import Lock
from fsdeploy.lib.scheduler.security.decorator import security


@security.rootfs.squashfs_mount(require_root=True)
class SquashfsMountTask(Task):
    """Monte une image SquashFS en readonly."""

    def required_locks(self):
        sfs = self.params.get("squashfs_path", "")
        return [Lock(f"squashfs.{Path(sfs).stem}", owner_id=str(self.id))]

    def run(self) -> dict[str, Any]:
        sfs_path = self.params.get("squashfs_path", "")
        mountpoint = self.params.get("mountpoint", "")

        if not sfs_path:
            raise ValueError("squashfs_path requis")
        if not Path(sfs_path).exists():
            raise FileNotFoundError(f"Image introuvable : {sfs_path}")

        if not mountpoint:
            mountpoint = f"/mnt/squashfs-{Path(sfs_path).stem}"

        mp = Path(mountpoint)
        mp.mkdir(parents=True, exist_ok=True)

        r = self.run_cmd(
            f"mount -t squashfs -o loop,ro {sfs_path} {mountpoint}",
            sudo=True, check=False, timeout=30,
        )
        if not r.success:
            raise RuntimeError(f"Mount squashfs echoue : {r.stderr}")

        return {
            "squashfs": sfs_path,
            "mountpoint": mountpoint,
            "mounted": True,
        }


@security.rootfs.overlay_setup(require_root=True)
class OverlaySetupTask(Task):
    """
    Cree un stack overlayfs complet.

    Params :
        lower: chemin du lower (squashfs monte ou dossier)
        upper: chemin du upper (ecriture) — cree si absent
        merged: chemin du merged (point de montage final)
        upper_type: "tmpfs" ou "zfs" (defaut: tmpfs)
        upper_dataset: dataset ZFS pour upper (si upper_type=zfs)
        tmpfs_size: taille tmpfs (defaut: "2G")
    """

    def required_locks(self):
        merged = self.params.get("merged", "/mnt/overlay")
        return [Lock(f"overlay.{Path(merged).name}", owner_id=str(self.id), exclusive=True)]

    def run(self) -> dict[str, Any]:
        lower = self.params.get("lower", "")
        upper = self.params.get("upper", "")
        merged = self.params.get("merged", "")
        upper_type = self.params.get("upper_type", "tmpfs")
        tmpfs_size = self.params.get("tmpfs_size", "2G")
        upper_dataset = self.params.get("upper_dataset", "")

        if not lower:
            raise ValueError("lower requis (squashfs mountpoint)")
        if not merged:
            raise ValueError("merged requis (point de montage final)")

        lower_path = Path(lower)
        if not lower_path.exists():
            raise FileNotFoundError(f"Lower introuvable : {lower}")

        # Determiner upper
        if not upper:
            upper = f"{merged}-upper"
        work = f"{upper}-work"

        # Creer les dossiers
        for d in [upper, work, merged]:
            Path(d).mkdir(parents=True, exist_ok=True)

        # Monter upper si tmpfs
        if upper_type == "tmpfs":
            r = self.run_cmd(
                f"mount -t tmpfs -o size={tmpfs_size} tmpfs {upper}",
                sudo=True, check=False, timeout=10,
            )
            if not r.success:
                raise RuntimeError(f"Mount tmpfs upper echoue : {r.stderr}")
            # Recreer work dans le tmpfs
            Path(work).mkdir(parents=True, exist_ok=True)

        elif upper_type == "zfs" and upper_dataset:
            r = self.run_cmd(
                f"mount -t zfs {upper_dataset} {upper}",
                sudo=True, check=False, timeout=30,
            )
            if not r.success:
                raise RuntimeError(f"Mount ZFS upper echoue : {r.stderr}")
            Path(work).mkdir(parents=True, exist_ok=True)

        # Monter overlayfs
        opts = f"lowerdir={lower},upperdir={upper},workdir={work}"
        r = self.run_cmd(
            f"mount -t overlay overlay -o {opts} {merged}",
            sudo=True, check=False, timeout=15,
        )
        if not r.success:
            raise RuntimeError(f"Mount overlay echoue : {r.stderr}")

        return {
            "lower": lower,
            "upper": upper,
            "work": work,
            "merged": merged,
            "upper_type": upper_type,
            "mounted": True,
        }


@security.rootfs.overlay_teardown(require_root=True)
class OverlayTeardownTask(Task):
    """Demonte un stack overlayfs proprement (merged -> upper -> lower)."""

    def required_locks(self):
        merged = self.params.get("merged", "/mnt/overlay")
        return [Lock(f"overlay.{Path(merged).name}", owner_id=str(self.id), exclusive=True)]

    def run(self) -> dict[str, Any]:
        merged = self.params.get("merged", "")
        upper = self.params.get("upper", "")
        lower = self.params.get("lower", "")
        cleanup_dirs = self.params.get("cleanup_dirs", False)

        errors = []

        # Demontage dans l'ordre inverse : merged -> upper -> lower
        for target, label in [(merged, "merged"), (upper, "upper"), (lower, "lower")]:
            if not target:
                continue
            r = self.run_cmd(
                f"umount {target}",
                sudo=True, check=False, timeout=15,
            )
            if not r.success:
                # Essayer umount lazy
                r2 = self.run_cmd(
                    f"umount -l {target}",
                    sudo=True, check=False, timeout=10,
                )
                if not r2.success:
                    errors.append(f"{label}: {r.stderr}")

        # Cleanup optionnel des dossiers
        if cleanup_dirs:
            work = self.params.get("work", "")
            for d in [merged, upper, work]:
                if d:
                    try:
                        Path(d).rmdir()
                    except OSError:
                        pass

        return {
            "merged": merged,
            "unmounted": len(errors) == 0,
            "errors": errors,
        }
```

## B. Créer `fsdeploy/lib/intents/overlay_intent.py`

```python
# -*- coding: utf-8 -*-
"""
Intents pour le montage SquashFS et la gestion overlay.
"""

from fsdeploy.lib.scheduler.model.intent import Intent
from fsdeploy.lib.scheduler.core.registry import register_intent


@register_intent("overlay.squashfs.mount")
class SquashfsMountIntent(Intent):
    def build_tasks(self):
        from fsdeploy.lib.function.rootfs.overlay import SquashfsMountTask
        return [SquashfsMountTask(
            id="squashfs_mount", params=self.params, context=self.context)]


@register_intent("overlay.setup")
class OverlaySetupIntent(Intent):
    def build_tasks(self):
        from fsdeploy.lib.function.rootfs.overlay import OverlaySetupTask
        return [OverlaySetupTask(
            id="overlay_setup", params=self.params, context=self.context)]


@register_intent("overlay.teardown")
class OverlayTeardownIntent(Intent):
    def build_tasks(self):
        from fsdeploy.lib.function.rootfs.overlay import OverlayTeardownTask
        return [OverlayTeardownTask(
            id="overlay_teardown", params=self.params, context=self.context)]


@register_intent("overlay.mount")
class OverlayFullMountIntent(Intent):
    """
    Mount complet : squashfs + overlay en une seule operation.
    Cree 2 tasks en sequence.
    """
    def build_tasks(self):
        from fsdeploy.lib.function.rootfs.overlay import (
            SquashfsMountTask, OverlaySetupTask,
        )
        sfs_path = self.params.get("squashfs_path", "")
        merged = self.params.get("merged", "")
        lower = self.params.get("lower", f"/mnt/squashfs-lower")

        return [
            SquashfsMountTask(
                id="squashfs_mount",
                params={"squashfs_path": sfs_path, "mountpoint": lower},
                context=self.context,
            ),
            OverlaySetupTask(
                id="overlay_setup",
                params={**self.params, "lower": lower, "merged": merged},
                context=self.context,
            ),
        ]
```

## C. Enregistrer dans `daemon.py`

Ajouter l'import dans `_register_all_intents()` du daemon :

```python
from fsdeploy.lib.intents import overlay_intent  # noqa
```

## Critères

1. `test -f fsdeploy/lib/function/rootfs/overlay.py` → existe
2. `test -f fsdeploy/lib/intents/overlay_intent.py` → existe
3. `grep "register_intent" fsdeploy/lib/intents/overlay_intent.py` → 4 intents (squashfs.mount, setup, teardown, mount)
4. `grep "overlay_intent" fsdeploy/lib/daemon.py` → importé dans _register_all_intents
5. `grep "mount -t overlay" fsdeploy/lib/function/rootfs/overlay.py` → commande overlay présente
6. `grep "mount -t squashfs" fsdeploy/lib/function/rootfs/overlay.py` → commande squashfs présente
