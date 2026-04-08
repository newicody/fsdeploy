"""
Détection des modules du noyau Linux (squashfs ou non) via recherche sur des partitions.
"""
import os
import re
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional

from fsdeploy.lib.scheduler.model.task import Task


class KernelModuleDetectTask(Task):
    """Détecte les modules du noyau sur le système, y compris dans des partitions squashfs."""

    def execute(self) -> Dict[str, Any]:
        self.log_event("kernel.module.detect.started", {"params": self.params})
        
        # Paramètres
        scan_paths = self.params.get("scan_paths", ["/lib/modules", "/run/initramfs"])
        squash_pattern = self.params.get("squash_pattern", r"\.squashfs$")
        partition_pattern = self.params.get("partition_pattern", r"^/dev/[a-z]+[0-9]*$")
        
        # Détection des partitions susceptibles
        partitions = self._find_partitions(partition_pattern)
        # Détection des fichiers squashfs
        squash_files = self._find_squashfs(scan_paths, squash_pattern)
        
        # Explorer chaque partition et squashfs pour trouver des modules
        modules = []
        for part in partitions:
            mods = self._scan_partition_for_modules(part)
            modules.extend(mods)
        
        for sq in squash_files:
            mods = self._scan_squashfs_for_modules(sq)
            modules.extend(mods)
        
        # Détection des modules déjà chargés
        loaded = self._get_loaded_modules()
        
        # Éliminer les doublons (même chemin)
        seen = set()
        unique_modules = []
        for mod in modules:
            key = mod.get("path")
            if key not in seen:
                seen.add(key)
                unique_modules.append(mod)
        
        result = {
            "detected_partitions": partitions,
            "detected_squashfs": squash_files,
            "modules_found": unique_modules,
            "loaded_modules": loaded,
            "total_found": len(unique_modules),
        }
        self.log_event("kernel.module.detect.completed", result)
        return result

    def _find_partitions(self, pattern: str) -> List[str]:
        """Retourne la liste des partitions correspondant au motif."""
        partitions = []
        # Essayer d'utiliser lsblk pour une liste plus précise
        try:
            out = subprocess.check_output(
                ["lsblk", "-ln", "-o", "NAME,TYPE"],
                text=True,
                stderr=subprocess.DEVNULL,
            )
            for line in out.strip().splitlines():
                parts = line.split()
                if len(parts) >= 2 and parts[1] == "part":
                    dev = "/dev/" + parts[0]
                    if re.match(pattern, dev):
                        partitions.append(dev)
        except Exception:
            # Fallback à la méthode précédente
            pass
        # Méthode de secours
        if not partitions:
            try:
                for entry in Path("/dev").iterdir():
                    if entry.is_block_device() and re.match(pattern, str(entry)):
                        partitions.append(str(entry))
            except Exception:
                pass
        return partitions

    def _find_squashfs(self, scan_paths: List[str], pattern: str) -> List[str]:
        """Recherche les fichiers squashfs dans les chemins donnés."""
        squash = []
        for base in scan_paths:
            bp = Path(base)
            if not bp.exists():
                continue
            for f in bp.rglob("*"):
                if f.is_file() and re.search(pattern, f.name):
                    squash.append(str(f))
        return squash

    def _scan_partition_for_modules(self, partition: str) -> List[Dict[str, Any]]:
        """Tente de monter la partition et scanner /lib/modules."""
        modules = []
        mountpoint = None
        try:
            mountpoint = tempfile.mkdtemp(prefix="fsdeploy_mnt_")
            # Monter la partition en lecture seule
            result = subprocess.run(
                ["mount", "-t", "auto", "-o", "ro,noatime", partition, mountpoint],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                self.log_event("kernel.module.detect.mount_failed",
                               {"partition": partition, "error": result.stderr})
                return modules
            # Scanner les répertoires connus pour les modules
            for mod_dir in ["lib/modules", "usr/lib/modules"]:
                scan_path = Path(mountpoint) / mod_dir
                if not scan_path.exists():
                    continue
                for version_dir in scan_path.iterdir():
                    if version_dir.is_dir():
                        for ko in version_dir.rglob("*.ko*"):
                            rel = ko.relative_to(scan_path)
                            modules.append({
                                "partition": partition,
                                "path": str(ko),
                                "version": version_dir.name,
                                "relative": str(rel),
                                "size": ko.stat().st_size,
                            })
        except Exception as e:
            self.log_event("kernel.module.detect.scan_error",
                           {"partition": partition, "exception": str(e)})
        finally:
            if mountpoint and Path(mountpoint).exists():
                try:
                    subprocess.run(["umount", mountpoint], capture_output=True)
                except Exception:
                    pass
                shutil.rmtree(mountpoint, ignore_errors=True)
        return modules

    def _scan_squashfs_for_modules(self, squash_path: str) -> List[Dict[str, Any]]:
        """Tente de monter le squashfs et scanner."""
        modules = []
        mountpoint = None
        try:
            mountpoint = tempfile.mkdtemp(prefix="fsdeploy_sq_")
            result = subprocess.run(
                ["mount", "-t", "squashfs", "-o", "ro", squash_path, mountpoint],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                self.log_event("kernel.module.detect.squash_mount_failed",
                               {"squash": squash_path, "error": result.stderr})
                return modules
            # Scanner les répertoires connus pour les modules
            for mod_dir in ["lib/modules", "usr/lib/modules"]:
                scan_path = Path(mountpoint) / mod_dir
                if not scan_path.exists():
                    continue
                for version_dir in scan_path.iterdir():
                    if version_dir.is_dir():
                        for ko in version_dir.rglob("*.ko*"):
                            rel = ko.relative_to(scan_path)
                            modules.append({
                                "squash": squash_path,
                                "path": str(ko),
                                "version": version_dir.name,
                                "relative": str(rel),
                                "size": ko.stat().st_size,
                            })
        except Exception as e:
            self.log_event("kernel.module.detect.squash_scan_error",
                           {"squash": squash_path, "exception": str(e)})
        finally:
            if mountpoint and Path(mountpoint).exists():
                try:
                    subprocess.run(["umount", mountpoint], capture_output=True)
                except Exception:
                    pass
                shutil.rmtree(mountpoint, ignore_errors=True)
        return modules

    def _get_loaded_modules(self) -> List[str]:
        """Retourne la liste des modules chargés (via lsmod)."""
        loaded = []
        try:
            out = subprocess.check_output(["lsmod"], text=True, stderr=subprocess.DEVNULL)
            # Première ligne est l'en-tête
            for line in out.splitlines()[1:]:
                if line.strip():
                    module = line.split()[0]
                    loaded.append(module)
        except Exception:
            pass
        return loaded
