"""
fsdeploy.function.detect.role_patterns
========================================
Détection du rôle des datasets par inspection de contenu.

Principe fondamental : AUCUN nom codé en dur.
Tout est détecté par patterns de fichiers et magic bytes.

Rôles supportés (15) :
  boot, kernel, initramfs, modules, rootfs, squashfs,
  efi, python_env, overlay, config, images, archive,
  snapshot, data, cache, log

Scoring multi-signaux :
  - Pattern matching (globs) : 40%
  - Magic bytes : 30%
  - Contenu spécifique : 20%
  - Heuristiques : 10%
"""

import os
import struct
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, field
from fnmatch import fnmatch


# ─── Définition des rôles ─────────────────────────────────────────────────────

@dataclass
class RolePattern:
    """Définition d'un rôle avec ses patterns de détection."""
    role: str
    globs: list[str]
    min_matches: int = 1
    priority: int = 0
    description: str = ""
    color: str = "white"
    emoji: str = "📁"
    ascii_icon: str = "[?]"


ROLE_PATTERNS: list[RolePattern] = [
    RolePattern(
        role="boot",
        globs=[
            "vmlinuz*", "bzImage*", "initramfs*", "initrd*",
            "EFI/**", "efi/**", "fsdeploy.conf", "grub/**",
            "loader/**", "syslinux/**",
        ],
        min_matches=2,
        priority=15,
        description="Partition/dataset de boot",
        color="green",
        emoji="🥾",
        ascii_icon="[B]",
    ),
    RolePattern(
        role="kernel",
        globs=[
            "vmlinuz-*", "vmlinux-*", "bzImage-*",
            "config-*", "System.map-*", "*.efi",
        ],
        min_matches=1,
        priority=14,
        description="Noyaux Linux",
        color="cyan",
        emoji="🐧",
        ascii_icon="[K]",
    ),
    RolePattern(
        role="initramfs",
        globs=[
            "initrd.img-*", "initramfs-*.img", "initramfs.img",
            "initrd-*.img", "initramfs*.cpio*",
        ],
        min_matches=1,
        priority=13,
        description="Images initramfs",
        color="blue",
        emoji="📦",
        ascii_icon="[I]",
    ),
    RolePattern(
        role="modules",
        globs=[
            "lib/modules/*/modules.dep",
            "lib/modules/*/*.ko",
            "lib/modules/*/*.ko.zst",
            "lib/modules/*/*.ko.xz",
            "modules-*.sfs",
        ],
        min_matches=1,
        priority=12,
        description="Modules noyau",
        color="magenta",
        emoji="🧩",
        ascii_icon="[M]",
    ),
    RolePattern(
        role="rootfs",
        globs=[
            "etc/os-release", "etc/passwd", "etc/fstab",
            "usr/bin/*", "usr/lib/*", "sbin/*", "bin/*",
        ],
        min_matches=3,
        priority=11,
        description="Système de fichiers racine",
        color="yellow",
        emoji="🌳",
        ascii_icon="[R]",
    ),
    RolePattern(
        role="squashfs",
        globs=[
            "*.sfs", "*.squashfs", "images/*.sfs",
            "rootfs.sfs", "python.sfs", "modules.sfs",
        ],
        min_matches=1,
        priority=10,
        description="Images SquashFS",
        color="red",
        emoji="📀",
        ascii_icon="[S]",
    ),
    RolePattern(
        role="efi",
        globs=[
            "EFI/BOOT/BOOTX64.EFI", "EFI/BOOT/bootx64.efi",
            "EFI/ZBM/*.EFI", "EFI/systemd/*.efi",
            "EFI/Linux/*.efi",
        ],
        min_matches=1,
        priority=9,
        description="Partition EFI",
        color="white",
        emoji="💾",
        ascii_icon="[E]",
    ),
    RolePattern(
        role="python_env",
        globs=[
            "bin/python3", "bin/python", "lib/python3*",
            "lib/python3*/site-packages/*", "pyvenv.cfg",
        ],
        min_matches=2,
        priority=8,
        description="Environnement Python",
        color="blue",
        emoji="🐍",
        ascii_icon="[P]",
    ),
    RolePattern(
        role="overlay",
        globs=[
            "upper/", "work/", "upper/*", "work/*",
        ],
        min_matches=2,
        priority=7,
        description="Overlay upper layer",
        color="cyan",
        emoji="📝",
        ascii_icon="[O]",
    ),
    RolePattern(
        role="config",
        globs=[
            "fsdeploy.conf", "*.conf", "config/*",
            "etc/fsdeploy/*", "presets/*.json",
        ],
        min_matches=1,
        priority=6,
        description="Configuration fsdeploy",
        color="yellow",
        emoji="⚙️",
        ascii_icon="[C]",
    ),
    RolePattern(
        role="images",
        globs=[
            "images/", "images/*.sfs", "images/*.img",
            "*.sfs", "rootfs.sfs", "python.sfs",
        ],
        min_matches=1,
        priority=5,
        description="Répertoire d'images",
        color="magenta",
        emoji="🖼️",
        ascii_icon="[i]",
    ),
    RolePattern(
        role="archive",
        globs=[
            "*.tar", "*.tar.gz", "*.tar.zst", "*.tar.xz",
            "*.zip", "backup/*", "archives/*",
        ],
        min_matches=1,
        priority=4,
        description="Archives",
        color="white",
        emoji="🗄️",
        ascii_icon="[A]",
    ),
    RolePattern(
        role="snapshot",
        globs=[
            ".zfs/snapshot/*", "@*",
        ],
        min_matches=1,
        priority=3,
        description="Snapshots ZFS",
        color="green",
        emoji="📸",
        ascii_icon="[Z]",
    ),
    RolePattern(
        role="cache",
        globs=[
            "cache/", "var/cache/*", ".cache/*",
            "apt/archives/*", "pip/*",
        ],
        min_matches=1,
        priority=2,
        description="Cache",
        color="white",
        emoji="⚡",
        ascii_icon="[c]",
    ),
    RolePattern(
        role="log",
        globs=[
            "log/", "var/log/*", "logs/*",
            "*.log", "journal/*",
        ],
        min_matches=1,
        priority=1,
        description="Logs",
        color="white",
        emoji="📋",
        ascii_icon="[L]",
    ),
    RolePattern(
        role="data",
        globs=["*"],
        min_matches=1,
        priority=0,
        description="Données génériques",
        color="white",
        emoji="📁",
        ascii_icon="[D]",
    ),
]


# ─── Magic bytes ──────────────────────────────────────────────────────────────

MAGIC_SIGNATURES = {
    # Linux kernel
    b"\x1f\x8b": "gzip",
    b"\xfd\x37\x7a\x58\x5a\x00": "xz",
    b"\x28\xb5\x2f\xfd": "zstd",
    b"\x4d\x5a": "dos_exe",  # peut être un kernel EFI
    # ELF
    b"\x7fELF": "elf",
    # SquashFS
    b"hsqs": "squashfs_le",
    b"sqsh": "squashfs_be",
    # CPIO (initramfs)
    b"070701": "cpio_newc",
    b"070702": "cpio_crc",
    # FAT/EFI
    b"\xeb\x3c\x90": "fat_boot",
    b"\xeb\x58\x90": "fat32_boot",
}


def detect_magic(filepath: Path) -> Optional[str]:
    """Détecte le type de fichier par magic bytes."""
    try:
        with open(filepath, "rb") as f:
            header = f.read(16)

        for magic, file_type in MAGIC_SIGNATURES.items():
            if header.startswith(magic):
                return file_type

        # Vérification spéciale pour kernel Linux
        if len(header) >= 4:
            # bzImage : magic à offset 0x202
            try:
                with open(filepath, "rb") as f:
                    f.seek(0x202)
                    kernel_magic = f.read(4)
                    if kernel_magic == b"HdrS":
                        return "linux_kernel"
            except Exception:
                pass

        return None
    except Exception:
        return None


# ─── Scoring ──────────────────────────────────────────────────────────────────

@dataclass
class DetectionSignal:
    """Signal de détection avec source et poids."""
    source: str  # "pattern", "magic", "content", "heuristic"
    role: str
    confidence: float  # 0.0 - 1.0
    detail: str = ""


@dataclass
class DetectionResult:
    """Résultat de détection pour un dataset."""
    dataset: str
    role: str
    confidence: float
    signals: list[DetectionSignal] = field(default_factory=list)
    details: str = ""


def compute_aggregate_confidence(signals: list[DetectionSignal]) -> tuple[str, float]:
    """
    Agrège les signaux pour déterminer le rôle final.
    
    Poids :
      - pattern: 40%
      - magic: 30%
      - content: 20%
      - heuristic: 10%
    """
    weights = {
        "pattern": 0.4,
        "magic": 0.3,
        "content": 0.2,
        "heuristic": 0.1,
    }

    # Grouper par rôle
    role_scores: dict[str, float] = {}
    for sig in signals:
        w = weights.get(sig.source, 0.1)
        score = sig.confidence * w
        role_scores[sig.role] = role_scores.get(sig.role, 0) + score

    if not role_scores:
        return "data", 0.0

    # Prendre le meilleur
    best_role = max(role_scores, key=role_scores.get)
    best_score = role_scores[best_role]

    # Normaliser (max théorique = 1.0)
    normalized = min(best_score, 1.0)

    return best_role, normalized


def scan_directory(root: Path, max_depth: int = 3) -> list[DetectionSignal]:
    """
    Scanne un répertoire et génère des signaux de détection.
    """
    signals: list[DetectionSignal] = []

    for pattern_def in ROLE_PATTERNS:
        matches = 0
        matched_files = []

        for glob_pattern in pattern_def.globs:
            # Limiter la profondeur
            try:
                if "**" in glob_pattern:
                    found = list(root.glob(glob_pattern))[:100]
                else:
                    found = list(root.glob(glob_pattern))[:50]

                for f in found:
                    # Vérifier la profondeur
                    rel = f.relative_to(root)
                    if len(rel.parts) <= max_depth:
                        matches += 1
                        matched_files.append(str(rel))
            except Exception:
                continue

        if matches >= pattern_def.min_matches:
            # Confidence basée sur le nombre de matches
            conf = min(1.0, matches / (pattern_def.min_matches * 2))
            signals.append(DetectionSignal(
                source="pattern",
                role=pattern_def.role,
                confidence=conf,
                detail=f"Matched {matches} files: {', '.join(matched_files[:3])}...",
            ))

    # Magic bytes sur les fichiers principaux
    for f in list(root.iterdir())[:20]:
        if f.is_file() and f.stat().st_size > 0:
            magic = detect_magic(f)
            if magic:
                # Mapper magic vers rôle
                role_map = {
                    "linux_kernel": "kernel",
                    "gzip": "initramfs",  # souvent initramfs compressé
                    "squashfs_le": "squashfs",
                    "squashfs_be": "squashfs",
                    "elf": "rootfs",
                    "cpio_newc": "initramfs",
                    "cpio_crc": "initramfs",
                }
                role = role_map.get(magic)
                if role:
                    signals.append(DetectionSignal(
                        source="magic",
                        role=role,
                        confidence=0.9,
                        detail=f"Magic bytes: {magic} in {f.name}",
                    ))

    return signals


# ─── Helpers pour la TUI ──────────────────────────────────────────────────────

def get_role_pattern(role: str) -> Optional[RolePattern]:
    """Récupère la définition d'un rôle."""
    for p in ROLE_PATTERNS:
        if p.role == role:
            return p
    return None


def get_role_color(role: str) -> str:
    """Couleur Textual pour un rôle."""
    p = get_role_pattern(role)
    return p.color if p else "white"


def get_role_emoji(role: str, ascii_fallback: bool = False) -> str:
    """Emoji ou icône ASCII pour un rôle."""
    p = get_role_pattern(role)
    if not p:
        return "[?]" if ascii_fallback else "📁"
    return p.ascii_icon if ascii_fallback else p.emoji


def get_role_description(role: str) -> str:
    """Description d'un rôle."""
    p = get_role_pattern(role)
    return p.description if p else "Unknown"


def format_role_badge(role: str, confidence: float, ascii_mode: bool = False) -> str:
    """Formate un badge rôle pour affichage."""
    icon = get_role_emoji(role, ascii_fallback=ascii_mode)
    pct = f"{confidence:.0%}"
    return f"{icon} {role} ({pct})"


# ─── Exports ──────────────────────────────────────────────────────────────────

__all__ = [
    "ROLE_PATTERNS",
    "RolePattern",
    "DetectionSignal",
    "DetectionResult",
    "MAGIC_SIGNATURES",
    "detect_magic",
    "scan_directory",
    "compute_aggregate_confidence",
    "get_role_pattern",
    "get_role_color",
    "get_role_emoji",
    "get_role_description",
    "format_role_badge",
]
