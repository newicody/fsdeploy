# -*- coding: utf-8 -*-
"""
fsdeploy.function.kernel.registry
====================================
Registre global de noyaux : inventaire cross-dataset.

Agregue les resultats de detection (DatasetProbeTask) pour construire
un catalogue unifie de tous les kernels, initramfs et modules
disponibles sur l'ensemble des datasets montes.

ZERO chemin en dur : tout est pilote par config, preset et params.
"""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Any

from scheduler.model.task import Task
from scheduler.model.resource import Resource, KERNEL
from scheduler.model.lock import Lock
from scheduler.security.decorator import security


# ===================================================================
# HELPERS (pur fonctionnel, pas de path en dur)
# ===================================================================

def _md5_file(path: Path, chunk_size: int = 65536) -> str:
    """Calcule le MD5 d'un fichier."""
    h = hashlib.md5()
    try:
        with path.open("rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                h.update(chunk)
    except (OSError, PermissionError):
        return ""
    return h.hexdigest()


def _extract_version(filename: str, prefixes: list[str]) -> str:
    """
    Extrait la version d'un nom de fichier kernel/initramfs.
    Ex: vmlinuz-6.12.0-amd64 -> 6.12.0-amd64
        initramfs-6.12.0.img -> 6.12.0
    """
    base = filename
    for prefix in prefixes:
        if base.startswith(prefix):
            base = base[len(prefix):]
            break

    # Retirer les suffixes connus
    for suffix in (".img", ".efi", ".cpio", ".cpio.gz", ".cpio.zst"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break

    return base


def _is_kernel_by_magic(path: Path) -> bool:
    """
    Verifie qu'un fichier est un kernel Linux par magic bytes.
    ELF header (\\x7fELF) ou bzImage header (HdrS a offset 0x202).
    """
    try:
        with path.open("rb") as f:
            header = f.read(0x210)
            if len(header) < 4:
                return False
            # ELF
            if header[:4] == b"\x7fELF":
                return True
            # bzImage
            if len(header) >= 0x206 and header[0x202:0x206] == b"HdrS":
                return True
    except (OSError, PermissionError):
        pass
    return False


def _find_matching_initramfs(
    kernel_version: str,
    search_dir: Path,
    initramfs_prefixes: list[str],
) -> str:
    """
    Cherche un initramfs correspondant a une version kernel
    dans le meme repertoire. Retourne le nom de fichier ou "".
    """
    if not search_dir.is_dir():
        return ""

    # Generer les candidats comme le fait zfsbootmenu-core.sh
    candidates = []
    for pfx in initramfs_prefixes:
        candidates.append(f"{pfx}{kernel_version}.img")
        candidates.append(f"{pfx}{kernel_version}")

    for candidate in candidates:
        if (search_dir / candidate).exists():
            return candidate

    # Recherche exhaustive : extensions variees
    for ext in ("", ".img", ".gz", ".xz", ".zstd", ".lz4"):
        for pfx in initramfs_prefixes:
            for name in (f"{pfx}{kernel_version}{ext}",
                         f"{pfx}{ext}{kernel_version}"):
                if (search_dir / name).exists():
                    return name

    return ""


def _find_modules_dir(
    kernel_version: str,
    mounts: dict[str, str],
) -> dict[str, str]:
    """
    Cherche un repertoire de modules correspondant a la version kernel
    dans tous les montages connus. Retourne {"path": ..., "dataset": ...} ou {}.
    """
    for dataset, mountpoint in mounts.items():
        mp = Path(mountpoint)
        mod_dir = mp / "lib" / "modules" / kernel_version
        if mod_dir.is_dir():
            modules_dep = mod_dir / "modules.dep"
            return {
                "path": str(mod_dir),
                "dataset": dataset,
                "has_dep": modules_dep.exists(),
                "version": kernel_version,
            }
    return {}


# ===================================================================
# KERNEL ENTRY (dataclass-like dict pour le registre)
# ===================================================================

def _build_entry(
    file_path: Path,
    dataset: str,
    mountpoint: str,
    kernel_prefixes: list[str],
    initramfs_prefixes: list[str],
    mounts: dict[str, str],
) -> dict[str, Any]:
    """Construit une entree de registre pour un kernel."""
    name = file_path.name
    version = _extract_version(name, kernel_prefixes)
    md5 = _md5_file(file_path)

    # Chemin relatif au montage
    rel_path = str(file_path.relative_to(mountpoint))

    # Initramfs associe
    initramfs_name = _find_matching_initramfs(
        version, file_path.parent, initramfs_prefixes)

    # Modules associes
    modules_info = _find_modules_dir(version, mounts)

    return {
        "file": name,
        "version": version,
        "md5": md5,
        "size": file_path.stat().st_size,
        "path": str(file_path),
        "rel_path": rel_path,
        "dataset": dataset,
        "mountpoint": mountpoint,
        "is_kernel": _is_kernel_by_magic(file_path),
        "initramfs": initramfs_name,
        "initramfs_path": str(file_path.parent / initramfs_name) if initramfs_name else "",
        "modules": modules_info,
        "is_duplicate": False,
        "duplicate_of": "",
    }


# ===================================================================
# TASKS
# ===================================================================

@security.kernel.registry
class KernelRegistryScanTask(Task):
    """
    Scanne tous les datasets (ou ceux specifies) pour construire
    un inventaire complet des kernels disponibles.

    Params attendus (tous depuis config/preset, aucun en dur) :
      - mounts: dict {dataset: mountpoint}     (depuis runtime/detection)
      - search_datasets: list[str]             (depuis config, vide = tous)
      - kernel_prefixes: list[str]             (depuis config)
      - initramfs_prefixes: list[str]          (depuis config)
      - extra_patterns: list[str]              (depuis config)
    """

    def run(self) -> dict[str, Any]:
        mounts = self.params.get("mounts", {})
        search_datasets = self.params.get("search_datasets", [])
        kernel_prefixes = self.params.get("kernel_prefixes",
                                          ["vmlinuz-", "vmlinux-", "bzImage-"])
        initramfs_prefixes = self.params.get("initramfs_prefixes",
                                              ["initramfs-", "initrd.img-", "initrd-"])
        extra_patterns = self.params.get("extra_patterns", [])

        # Filtrer les datasets si search_datasets est specifie
        if search_datasets:
            targets = {ds: mp for ds, mp in mounts.items()
                       if ds in search_datasets}
        else:
            targets = dict(mounts)

        if not targets:
            return {"kernels": [], "count": 0, "error": "no datasets to scan"}

        # Construire les globs de recherche
        glob_patterns = []
        for pfx in kernel_prefixes:
            glob_patterns.append(f"{pfx}*")
        for pat in extra_patterns:
            glob_patterns.append(pat)

        # Scanner chaque dataset
        all_entries: list[dict[str, Any]] = []
        md5_map: dict[str, str] = {}  # md5 -> premier path

        for dataset, mountpoint in targets.items():
            mp = Path(mountpoint)
            if not mp.is_dir():
                continue

            for glob_pat in glob_patterns:
                # Chercher a la racine et un niveau en dessous
                for search_path in (mp, ):
                    for found in sorted(search_path.glob(glob_pat)):
                        if not found.is_file():
                            continue
                        # Verifier magic bytes
                        if not _is_kernel_by_magic(found):
                            continue

                        entry = _build_entry(
                            found, dataset, mountpoint,
                            kernel_prefixes, initramfs_prefixes, mounts,
                        )

                        # Dedup MD5
                        if entry["md5"] and entry["md5"] in md5_map:
                            entry["is_duplicate"] = True
                            entry["duplicate_of"] = md5_map[entry["md5"]]
                        elif entry["md5"]:
                            md5_map[entry["md5"]] = entry["path"]

                        all_entries.append(entry)

                    # Chercher aussi dans les sous-repertoires directs
                    for subdir in sorted(mp.iterdir()):
                        if not subdir.is_dir():
                            continue
                        for found in sorted(subdir.glob(glob_pat)):
                            if not found.is_file():
                                continue
                            if not _is_kernel_by_magic(found):
                                continue

                            entry = _build_entry(
                                found, dataset, mountpoint,
                                kernel_prefixes, initramfs_prefixes, mounts,
                            )

                            if entry["md5"] and entry["md5"] in md5_map:
                                entry["is_duplicate"] = True
                                entry["duplicate_of"] = md5_map[entry["md5"]]
                            elif entry["md5"]:
                                md5_map[entry["md5"]] = entry["path"]

                            all_entries.append(entry)

        # Trier : non-doublons d'abord, puis par version decroissante
        all_entries.sort(key=lambda e: (
            e["is_duplicate"],
            not e["version"],  # vides en dernier
            [-int(x) if x.isdigit() else 0
             for x in re.split(r"[.\-]", e["version"])[:4]],
        ))

        return {
            "kernels": all_entries,
            "count": len(all_entries),
            "unique": sum(1 for e in all_entries if not e["is_duplicate"]),
            "duplicates": sum(1 for e in all_entries if e["is_duplicate"]),
            "datasets_scanned": list(targets.keys()),
        }
