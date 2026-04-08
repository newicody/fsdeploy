# -*- coding: utf-8 -*-
"""
fsdeploy.function.kernel.provision
=====================================
Provisionnement de noyaux : transporte un kernel detecte dans un
dataset source vers le repertoire de staging (boot).

Trois methodes configurables :
  - symlink : lien symbolique relatif (meme pool / meme arborescence)
  - copy    : copie physique (cross-pool ou securite)
  - bind    : mount --bind (temporaire, utile pour test)

ZERO chemin en dur. Tous les paths proviennent de config/preset/params.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

from scheduler.model.task import Task
from scheduler.model.resource import Resource, KERNEL
from scheduler.model.lock import Lock
from scheduler.security.decorator import security


# ===================================================================
# HELPERS
# ===================================================================

def _resolve_staging_dir(params: dict) -> Path:
    """
    Resout le repertoire de staging.
    Priorite : params["staging_dir"] > config kernel.staging_dir > boot_mount.
    """
    staging = params.get("staging_dir", "")
    if staging:
        return Path(staging)
    boot_mount = params.get("boot_mount", "")
    if boot_mount:
        return Path(boot_mount)
    raise ValueError(
        "staging_dir or boot_mount required (config kernel.staging_dir "
        "or pool.boot_mount)"
    )


def _compute_relative_symlink(source: Path, target_dir: Path) -> str:
    """
    Calcule le chemin relatif pour un symlink.
    source     = /mnt/boot/images/vmlinuz-6.12.0
    target_dir = /mnt/boot/
    -> images/vmlinuz-6.12.0
    """
    try:
        return str(source.relative_to(target_dir))
    except ValueError:
        # Cross-mount : utiliser os.path.relpath
        return os.path.relpath(str(source), str(target_dir))


def _same_mountpoint(path_a: Path, path_b: Path) -> bool:
    """Verifie si deux paths sont sur le meme point de montage."""
    try:
        return os.stat(str(path_a)).st_dev == os.stat(str(path_b)).st_dev
    except OSError:
        return False


# ===================================================================
# TASKS
# ===================================================================

@security.kernel.provision
class KernelProvisionTask(Task):
    """
    Provisionne un kernel depuis sa source vers staging_dir.

    Params attendus (tous depuis config/preset, aucun en dur) :
      - source_path: str       Chemin absolu du kernel source
      - staging_dir: str       Repertoire cible (ou boot_mount en fallback)
      - boot_mount: str        Point de montage boot (fallback staging_dir)
      - install_method: str    "symlink" | "copy" | "bind"
      - version: str           Version du kernel (pour nommage)
      - provision_initramfs: bool  Aussi provisionner l'initramfs associe
      - initramfs_source: str  Chemin absolu de l'initramfs source (optionnel)
      - provision_modules: bool  Aussi provisionner les modules
      - modules_source: str    Chemin absolu des modules source (optionnel)
      - force: bool            Ecraser si existe deja
    """

    def required_resources(self):
        return [KERNEL]

    def required_locks(self):
        return [Lock("kernel", owner_id=str(self.id))]

    def run(self) -> dict[str, Any]:
        source_path = Path(self.params.get("source_path", ""))
        if not source_path.is_file():
            raise FileNotFoundError(
                f"Kernel source not found: {source_path}")

        staging = _resolve_staging_dir(self.params)
        method = self.params.get("install_method", "symlink")
        version = self.params.get("version", "")
        force = self.params.get("force", False)

        result = {
            "method": method,
            "version": version,
            "provisioned": [],
            "skipped": [],
            "errors": [],
        }

        # Provisionner le kernel
        kernel_result = self._provision_file(
            source_path, staging, method, force)
        result["provisioned"].append(kernel_result)
        result["kernel_staged"] = kernel_result.get("dest", "")

        # Provisionner l'initramfs si demande
        if self.params.get("provision_initramfs", False):
            initramfs_src = self.params.get("initramfs_source", "")
            if initramfs_src and Path(initramfs_src).is_file():
                ir_result = self._provision_file(
                    Path(initramfs_src), staging, method, force)
                result["provisioned"].append(ir_result)
                result["initramfs_staged"] = ir_result.get("dest", "")
            else:
                result["skipped"].append({
                    "type": "initramfs",
                    "reason": "source not found or not specified",
                    "path": initramfs_src,
                })

        # Provisionner les modules si demande
        if self.params.get("provision_modules", False):
            modules_src = self.params.get("modules_source", "")
            if modules_src and Path(modules_src).is_dir():
                mod_result = self._provision_modules(
                    Path(modules_src), staging, method, version, force)
                result["provisioned"].append(mod_result)
                result["modules_staged"] = mod_result.get("dest", "")
            else:
                result["skipped"].append({
                    "type": "modules",
                    "reason": "source not found or not specified",
                    "path": modules_src,
                })

        return result

    def _provision_file(
        self,
        source: Path,
        staging: Path,
        method: str,
        force: bool,
    ) -> dict[str, Any]:
        """Provisionne un fichier unique."""
        dest = staging / source.name

        if dest.exists() or dest.is_symlink():
            if not force:
                return {
                    "file": source.name,
                    "dest": str(dest),
                    "action": "skipped",
                    "reason": "already exists (use force=true to overwrite)",
                }
            # Supprimer l'existant
            if dest.is_symlink() or dest.is_file():
                dest.unlink()

        staging.mkdir(parents=True, exist_ok=True)

        if method == "symlink":
            return self._do_symlink(source, dest, staging)
        elif method == "copy":
            return self._do_copy(source, dest)
        elif method == "bind":
            return self._do_bind(source, dest)
        else:
            raise ValueError(f"Unknown install_method: {method}")

    def _do_symlink(
        self, source: Path, dest: Path, staging: Path,
    ) -> dict[str, Any]:
        """Cree un symlink relatif."""
        # Verifier si on est sur le meme filesystem
        if not _same_mountpoint(source, staging):
            # Cross-device : fallback copy avec avertissement
            result = self._do_copy(source, dest)
            result["warning"] = (
                "cross-device symlink not possible, fell back to copy"
            )
            result["original_method"] = "symlink"
            return result

        rel = _compute_relative_symlink(source, staging)
        dest.symlink_to(rel)
        return {
            "file": source.name,
            "dest": str(dest),
            "action": "symlink",
            "target": rel,
        }

    def _do_copy(
        self, source: Path, dest: Path,
    ) -> dict[str, Any]:
        """Copie physique avec sudo si necessaire."""
        try:
            shutil.copy2(str(source), str(dest))
        except PermissionError:
            self.run_cmd(
                f"cp -a {source} {dest}", sudo=True)
        return {
            "file": source.name,
            "dest": str(dest),
            "action": "copy",
            "size": dest.stat().st_size if dest.exists() else 0,
        }

    def _do_bind(
        self, source: Path, dest: Path,
    ) -> dict[str, Any]:
        """Mount --bind (temporaire)."""
        # Creer un fichier vide comme point de montage
        dest.touch()
        self.run_cmd(
            f"mount --bind {source} {dest}", sudo=True)
        return {
            "file": source.name,
            "dest": str(dest),
            "action": "bind",
        }

    def _provision_modules(
        self,
        source: Path,
        staging: Path,
        method: str,
        version: str,
        force: bool,
    ) -> dict[str, Any]:
        """Provisionne un repertoire de modules."""
        # Les modules vont dans staging/lib/modules/<version>/
        dest_base = staging / "lib" / "modules"
        if version:
            dest = dest_base / version
        else:
            dest = dest_base / source.name

        if dest.exists():
            if not force:
                return {
                    "file": str(source),
                    "dest": str(dest),
                    "action": "skipped",
                    "reason": "already exists",
                }
            # Supprimer
            self.run_cmd(f"rm -rf {dest}", sudo=True, check=False)

        dest_base.mkdir(parents=True, exist_ok=True)

        if method == "symlink" and _same_mountpoint(source, staging):
            rel = _compute_relative_symlink(source, dest.parent)
            dest.symlink_to(rel)
            return {
                "file": str(source),
                "dest": str(dest),
                "action": "symlink",
                "target": rel,
            }
        else:
            self.run_cmd(f"cp -a {source} {dest}", sudo=True)
            return {
                "file": str(source),
                "dest": str(dest),
                "action": "copy",
            }


@security.kernel.provision
class KernelUnprovisionTask(Task):
    """
    Retire un kernel provisionne du staging_dir.

    Params :
      - staging_dir / boot_mount : repertoire de staging
      - filename: str  nom du fichier a retirer
      - cleanup_initramfs: bool
      - cleanup_modules: bool
      - version: str
    """

    def required_resources(self):
        return [KERNEL]

    def required_locks(self):
        return [Lock("kernel", owner_id=str(self.id))]

    def run(self) -> dict[str, Any]:
        staging = _resolve_staging_dir(self.params)
        filename = self.params.get("filename", "")
        version = self.params.get("version", "")
        removed = []

        if not filename:
            raise ValueError("filename required")

        target = staging / filename
        if target.exists() or target.is_symlink():
            target.unlink()
            removed.append(str(target))

        # Cleanup initramfs
        if self.params.get("cleanup_initramfs", False) and version:
            for pfx in ("initramfs-", "initrd.img-", "initrd-"):
                for ext in ("", ".img"):
                    ir = staging / f"{pfx}{version}{ext}"
                    if ir.exists() or ir.is_symlink():
                        ir.unlink()
                        removed.append(str(ir))

        # Cleanup modules
        if self.params.get("cleanup_modules", False) and version:
            mod_dir = staging / "lib" / "modules" / version
            if mod_dir.exists() or mod_dir.is_symlink():
                if mod_dir.is_symlink():
                    mod_dir.unlink()
                else:
                    self.run_cmd(f"rm -rf {mod_dir}", sudo=True, check=False)
                removed.append(str(mod_dir))

        return {
            "filename": filename,
            "version": version,
            "removed": removed,
        }
