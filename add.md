# add.md — 23.1 : Créer `lib/scheduler/core/isolation.py`

## Quoi

Créer le module d'isolation qui fournit deux mécanismes :
1. **MountIsolation** — exécute des commandes dans un mount namespace isolé (mounts auto-nettoyés à la sortie)
2. **CgroupLimits** — crée un cgroup v2 avec limites CPU/mémoire pour un processus

## Fichier à créer : `fsdeploy/lib/scheduler/core/isolation.py`

```python
# -*- coding: utf-8 -*-
"""
fsdeploy.scheduler.core.isolation
====================================
Isolation des taches via namespaces Linux et cgroups v2.

MountIsolation : execute des commandes dans un mount namespace isole.
    Les mounts sont automatiquement nettoyes quand le namespace se ferme.
    Utilise `unshare --mount` — necessite root/sudo.

CgroupLimits : cree un cgroup v2 avec limites CPU/memoire.
    Utilise le filesystem cgroupfs (/sys/fs/cgroup/).

Usage :
    # Mount namespace pour probe temporaire
    iso = MountIsolation(sudo=True)
    result = iso.run(["mount", "-t", "zfs", "tank/boot", "/tmp/probe"],
                     ["ls", "/tmp/probe"],
                     ["umount", "/tmp/probe"])

    # Cgroup pour compilation kernel
    with CgroupLimits("fsdeploy-compile", cpu_percent=50, mem_max_mb=4096) as cg:
        proc = subprocess.Popen(["make", "-j4"])
        cg.attach(proc.pid)
        proc.wait()
"""

import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Optional

log = logging.getLogger(__name__)

# ======================================================================
# MOUNT NAMESPACE
# ======================================================================

class MountIsolation:
    """
    Execute des commandes dans un mount namespace isole.

    Tous les mounts effectues dans le namespace sont automatiquement
    nettoyes quand le processus fils se termine, meme en cas de crash.
    """

    def __init__(self, sudo: bool = True):
        self.sudo = sudo
        self._unshare = shutil.which("unshare")

    @property
    def available(self) -> bool:
        """Verifie que unshare est disponible."""
        return self._unshare is not None

    def run(self, *commands: list[str], timeout: int = 120) -> dict[str, Any]:
        """
        Execute une sequence de commandes dans un mount namespace.

        Args:
            *commands: Chaque argument est une liste de str (une commande).
            timeout: Timeout global en secondes.

        Returns:
            {"success": bool, "stdout": str, "stderr": str, "returncode": int}
        """
        if not self.available:
            return {"success": False, "error": "unshare not found",
                    "stdout": "", "stderr": "", "returncode": -1}

        # Construire un script bash qui execute toutes les commandes
        script_parts = ["set -e"]
        # Rendre les mounts prives pour eviter la propagation
        script_parts.append("mount --make-rprivate / 2>/dev/null || true")
        for cmd in commands:
            if isinstance(cmd, list):
                escaped = " ".join(f"'{c}'" if " " in c else c for c in cmd)
            else:
                escaped = str(cmd)
            script_parts.append(escaped)

        script = "\n".join(script_parts)

        # Construire la commande unshare
        unshare_cmd = []
        if self.sudo and os.geteuid() != 0:
            unshare_cmd = ["sudo", "-n"]
        unshare_cmd.extend([
            self._unshare, "--mount", "--propagation", "private",
            "bash", "-c", script,
        ])

        try:
            result = subprocess.run(
                unshare_cmd,
                capture_output=True, text=True,
                timeout=timeout,
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "timeout",
                    "stdout": "", "stderr": "", "returncode": -1}
        except Exception as e:
            return {"success": False, "error": str(e),
                    "stdout": "", "stderr": "", "returncode": -1}

    def probe_dataset(self, dataset: str, scan_script: str,
                      mountpoint: str = "", timeout: int = 60) -> dict:
        """
        Monte un dataset ZFS dans un namespace isole, execute un script
        de scan, et retourne le resultat. Le mount est auto-nettoye.

        Args:
            dataset: Nom du dataset ZFS (ex: "boot_pool/boot")
            scan_script: Script bash a executer apres le mount.
                        La variable $MP contient le mountpoint.
            mountpoint: Mountpoint (auto-genere si vide).
            timeout: Timeout en secondes.
        """
        if not mountpoint:
            mountpoint = f"/tmp/fsdeploy-probe-{dataset.replace('/', '-')}"

        script = (
            f"MP='{mountpoint}'\n"
            f"mkdir -p \"$MP\"\n"
            f"mount -t zfs '{dataset}' \"$MP\"\n"
            f"{scan_script}\n"
            f"umount \"$MP\" 2>/dev/null || true\n"
            f"rmdir \"$MP\" 2>/dev/null || true\n"
        )

        cmd = []
        if self.sudo and os.geteuid() != 0:
            cmd = ["sudo", "-n"]
        cmd.extend([
            self._unshare or "unshare",
            "--mount", "--propagation", "private",
            "bash", "-c", script,
        ])

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout,
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "dataset": dataset,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "timeout", "dataset": dataset}
        except Exception as e:
            return {"success": False, "error": str(e), "dataset": dataset}


# ======================================================================
# CGROUPS V2
# ======================================================================

CGROUP_ROOT = Path("/sys/fs/cgroup")


class CgroupLimits:
    """
    Cree un cgroup v2 avec limites CPU et memoire.

    Usage context manager :
        with CgroupLimits("fsdeploy-compile", cpu_percent=50, mem_max_mb=4096) as cg:
            proc = subprocess.Popen(...)
            cg.attach(proc.pid)
            proc.wait()
        # cgroup auto-supprime a la sortie
    """

    def __init__(self, name: str, cpu_percent: int = 100,
                 mem_max_mb: int = 0, sudo: bool = True):
        self.name = name
        self.cpu_percent = cpu_percent
        self.mem_max_mb = mem_max_mb
        self.sudo = sudo
        self.path = CGROUP_ROOT / "fsdeploy" / name
        self._created = False

    @classmethod
    def available(cls) -> bool:
        """Verifie que cgroups v2 est monte."""
        return (CGROUP_ROOT / "cgroup.controllers").exists()

    def create(self) -> bool:
        """Cree le cgroup et applique les limites."""
        if not self.available():
            log.warning("cgroups v2 non disponible")
            return False

        try:
            # Creer la hierarchie fsdeploy/ si besoin
            parent = CGROUP_ROOT / "fsdeploy"
            if not parent.exists():
                self._sudo_run(["mkdir", "-p", str(parent)])
                # Activer les controleurs dans le parent
                controllers = (CGROUP_ROOT / "cgroup.subtree_control").read_text().strip()
                if "cpu" not in controllers or "memory" not in controllers:
                    self._sudo_write(
                        CGROUP_ROOT / "cgroup.subtree_control",
                        "+cpu +memory",
                    )
                self._sudo_write(
                    parent / "cgroup.subtree_control",
                    "+cpu +memory",
                )

            # Creer le cgroup de la tache
            if not self.path.exists():
                self._sudo_run(["mkdir", "-p", str(self.path)])
                self._created = True

            # Appliquer limites CPU (cpu.max: quota period)
            if self.cpu_percent < 100:
                period = 100000  # 100ms
                quota = int(period * self.cpu_percent / 100)
                self._sudo_write(self.path / "cpu.max", f"{quota} {period}")

            # Appliquer limites memoire
            if self.mem_max_mb > 0:
                mem_bytes = self.mem_max_mb * 1024 * 1024
                self._sudo_write(self.path / "memory.max", str(mem_bytes))

            log.info(f"cgroup cree: {self.path} (cpu={self.cpu_percent}%, "
                     f"mem={self.mem_max_mb}MB)")
            return True

        except Exception as e:
            log.error(f"Erreur creation cgroup: {e}")
            return False

    def attach(self, pid: int) -> bool:
        """Deplace un processus dans le cgroup."""
        try:
            self._sudo_write(self.path / "cgroup.procs", str(pid))
            log.info(f"PID {pid} attache au cgroup {self.name}")
            return True
        except Exception as e:
            log.error(f"Erreur attach cgroup: {e}")
            return False

    def cleanup(self) -> None:
        """Supprime le cgroup."""
        if self._created and self.path.exists():
            try:
                self._sudo_run(["rmdir", str(self.path)])
                log.info(f"cgroup supprime: {self.path}")
            except Exception:
                pass

    def _sudo_write(self, path: Path, content: str) -> None:
        """Ecrit dans un fichier cgroup (avec sudo si necessaire)."""
        if self.sudo and os.geteuid() != 0:
            subprocess.run(
                ["sudo", "-n", "tee", str(path)],
                input=content, capture_output=True, text=True,
                timeout=5,
            )
        else:
            path.write_text(content)

    def _sudo_run(self, cmd: list[str]) -> None:
        """Execute une commande avec sudo si necessaire."""
        if self.sudo and os.geteuid() != 0:
            cmd = ["sudo", "-n"] + cmd
        subprocess.run(cmd, capture_output=True, timeout=10)

    def __enter__(self):
        self.create()
        return self

    def __exit__(self, *args):
        self.cleanup()
```

## Critères

1. `test -f fsdeploy/lib/scheduler/core/isolation.py` → existe
2. `grep "class MountIsolation" fsdeploy/lib/scheduler/core/isolation.py` → présent
3. `grep "class CgroupLimits" fsdeploy/lib/scheduler/core/isolation.py` → présent
4. `grep "unshare.*mount" fsdeploy/lib/scheduler/core/isolation.py` → présent
5. `grep "cpu.max\|memory.max" fsdeploy/lib/scheduler/core/isolation.py` → présent
6. Aucun import circulaire (le module est autonome, n'importe que stdlib)
