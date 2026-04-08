"""
fsdeploy.function.detect.role_patterns
========================================
Patterns de détection de rôles pour datasets ZFS.

15 rôles étendus avec priorités et scoring pondéré.
"""

from pathlib import Path
from typing import Any


# ═══════════════════════════════════════════════════════════════════
# ROLE PATTERNS — 15 rôles détectés
# ═══════════════════════════════════════════════════════════════════

ROLE_PATTERNS = [
    {
        "role": "boot",
        "globs": [
            "vmlinuz-*",           # kernels
            "initrd.img-*",        # initramfs
            "config-*",            # kernel configs
            "System.map-*",        # symbol maps
            "grub/",               # GRUB (si présent)
            "efi/",                # EFI (si présent)
        ],
        "min": 2,                  # au moins 2 matches requis
        "prio": 15,                # priorité la plus haute
        "description": "Boot partition avec kernels et initramfs",
    },
    {
        "role": "kernel",
        "globs": [
            "vmlinuz-*",
            "vmlinux-*",
            "bzImage-*",
            "*.efi",               # EFI bundles
        ],
        "min": 1,
        "prio": 14,
        "description": "Kernels Linux uniquement",
    },
    {
        "role": "initramfs",
        "globs": [
            "initrd.img-*",
            "initramfs-*.img",
            "initrd-*.img",
            "*.cpio",
            "*.cpio.gz",
        ],
        "min": 1,
        "prio": 13,
        "description": "Initramfs images",
    },
    {
        "role": "squashfs",
        "globs": [
            "*.sfs",
            "*.squashfs",
            "*.sqfs",
            "filesystem.squashfs",
        ],
        "min": 1,
        "prio": 12,
        "description": "Images squashfs (rootfs, modules, etc.)",
    },
    {
        "role": "modules",
        "globs": [
            "lib/modules/*",
            "modules/*/kernel/",
            "lib/modules/*/modules.dep",
        ],
        "min": 1,
        "prio": 11,
        "description": "Modules kernel",
    },
    {
        "role": "rootfs",
        "globs": [
            "bin/bash",
            "etc/fstab",
            "usr/bin/",
            "var/log/",
            "sbin/init",
            "lib/systemd/",
        ],
        "min": 3,
        "prio": 10,
        "description": "Système de fichiers racine complet",
    },
    {
        "role": "overlay",
        "globs": [
            "upper/",
            "work/",
            "merged/",
            ".overlay/",
        ],
        "min": 2,
        "prio": 9,
        "description": "Couche supérieure overlayfs",
    },
    {
        "role": "python_env",
        "globs": [
            "bin/python*",
            "lib/python*/",
            "pyvenv.cfg",
            "bin/pip*",
            "lib/python*/site-packages/",
        ],
        "min": 2,
        "prio": 8,
        "description": "Environnement virtuel Python",
    },
    {
        "role": "efi",
        "globs": [
            "EFI/",
            "*.efi",
            "grubx64.efi",
            "shimx64.efi",
            "EFI/BOOT/",
        ],
        "min": 1,
        "prio": 7,
        "description": "Partition EFI",
    },
    {
        "role": "home",
        "globs": [
            "home/*/*",           # /home/user/quelquechose
            "home/*/.bashrc",
            "home/*/.profile",
            "home/*/.config/",
            "*/Documents/",
            "*/Downloads/",
        ],
        "min": 2,
        "prio": 6,
        "description": "Répertoires utilisateurs",
    },
    {
        "role": "archive",
        "globs": [
            "*.tar.gz",
            "*.tar.xz",
            "*.tar.bz2",
            "*.zip",
            "backup/*",
            "archives/*",
            "*.7z",
            "*.rar",
        ],
        "min": 2,
        "prio": 5,
        "description": "Archives et backups",
    },
    {
        "role": "snapshot",
        "globs": [
            "@*",                  # snapshot ZFS standard
            ".zfs/snapshot/",
            "snapshot/*",
            "@[0-9]*",            # snapshot avec timestamp
        ],
        "min": 1,
        "prio": 4,
        "description": "Snapshots ZFS",
    },
    {
        "role": "data",
        "globs": [
            "data/*",
            "storage/*",
            "share/*",
            "media/*",
            "files/*",
        ],
        "min": 1,
        "prio": 3,
        "description": "Données génériques",
    },
    {
        "role": "cache",
        "globs": [
            "var/cache/*",
            "tmp/*",
            "cache/*",
            ".cache/",
            "*/cache/",
        ],
        "min": 1,
        "prio": 2,
        "description": "Caches temporaires",
    },
    {
        "role": "log",
        "globs": [
            "var/log/*",
            "*.log",
            "logs/*",
            "var/log/*.log",
            "syslog",
        ],
        "min": 1,
        "prio": 1,
        "description": "Fichiers de log",
    },
    {
        "role": "btrfs",
        "globs": [
            "@*",                  # subvolumes btrfs communs
            ".snapshots/",
            "var/lib/machines/",   # typique pour btrfs avec systemd-nspawn
            "btrfs/",
            "btrfs_subvol/*",
        ],
        "min": 1,
        "prio": 5,
        "description": "Système de fichiers BTRFS (subvolumes)",
    },
    {
        "role": "xfs",
        "globs": [
            "xfs/",
            ".xfs/",
            "var/log/xfs/",
            "xfs_meta/*",
        ],
        "min": 1,
        "prio": 4,
        "description": "Système de fichiers XFS",
    },
]


# ═══════════════════════════════════════════════════════════════════
# FONCTIONS DE SCORING
# ═══════════════════════════════════════════════════════════════════

def score_patterns(path: Path, patterns: list[dict] = None) -> tuple[str, float, dict]:
    """
    Score un path contre les ROLE_PATTERNS.
    
    Returns:
        (role, confidence, details)
        
        role: str — Le rôle détecté (ou "data" par défaut)
        confidence: float — Score 0.0-1.0
        details: dict — Matches trouvés, pattern utilisé, etc.
    """
    if patterns is None:
        patterns = ROLE_PATTERNS
    
    best = {"role": "data", "score": 0.0, "details": {}, "prio": -1}
    
    for pattern in patterns:
        matches = []
        for glob_pattern in pattern["globs"]:
            try:
                found = list(path.glob(glob_pattern))[:20]  # limite 20 pour perf
                if found:
                    matches.append({
                        "pattern": glob_pattern,
                        "count": len(found),
                        "samples": [str(f.relative_to(path)) for f in found[:3]],
                    })
            except (OSError, PermissionError):
                # Ignore les erreurs de permissions
                continue
        
        # Score brut : ratio matches / total globs
        score_raw = len(matches) / max(len(pattern["globs"]), 1)
        
        # Seuil minimal : au moins pattern["min"] globs doivent matcher
        if len(matches) < pattern["min"]:
            continue
        
        # Priorité : en cas d'égalité de score, prendre le rôle prioritaire
        if (pattern["prio"] > best["prio"] or
                (pattern["prio"] == best["prio"] and score_raw > best["score"])):
            best = {
                "role": pattern["role"],
                "score": score_raw,
                "details": {
                    "matches": matches,
                    "pattern_name": pattern["role"],
                    "description": pattern["description"],
                },
                "prio": pattern["prio"],
            }
    
    return best["role"], best["score"], best["details"]


def get_role_info(role: str) -> dict[str, Any]:
    """Retourne les infos d'un rôle."""
    for pattern in ROLE_PATTERNS:
        if pattern["role"] == role:
            return {
                "role": role,
                "globs": pattern["globs"],
                "min": pattern["min"],
                "prio": pattern["prio"],
                "description": pattern["description"],
            }
    
    return {
        "role": "unknown",
        "globs": [],
        "min": 0,
        "prio": 0,
        "description": "Rôle inconnu",
    }


def list_all_roles() -> list[str]:
    """Liste tous les rôles disponibles (triés par priorité)."""
    return [p["role"] for p in sorted(ROLE_PATTERNS, key=lambda x: x["prio"], reverse=True)]


def get_role_color(role: str) -> str:
    """
    Retourne une couleur Textual pour un rôle.
    
    Utilisé pour l'affichage dans la TUI.
    """
    ROLE_COLORS = {
        "boot": "cyan",
        "kernel": "blue",
        "initramfs": "magenta",
        "squashfs": "yellow",
        "modules": "green",
        "rootfs": "bright_cyan",
        "overlay": "bright_yellow",
        "python_env": "bright_green",
        "efi": "bright_magenta",
        "home": "bright_blue",
        "archive": "dim cyan",
        "snapshot": "dim yellow",
        "data": "white",
        "cache": "dim white",
        "log": "dim green",
        "btrfs": "bright_cyan",
        "xfs": "bright_red",
    }
    
    return ROLE_COLORS.get(role, "white")


def get_role_emoji(role: str) -> str:
    """
    Retourne un emoji pour un rôle.
    
    Utilisé pour l'affichage dans la TUI (mode ASCII fallback si TERM=linux).
    """
    ROLE_EMOJIS = {
        "boot": "🥾",
        "kernel": "🐧",
        "initramfs": "📦",
        "squashfs": "🗜️",
        "modules": "🧩",
        "rootfs": "🌳",
        "overlay": "📚",
        "python_env": "🐍",
        "efi": "⚡",
        "home": "🏠",
        "archive": "📁",
        "snapshot": "📸",
        "data": "💾",
        "cache": "⏱️",
        "log": "📝",
        "btrfs": "🌲",
        "xfs": "📊",
    }
    
    # Fallback ASCII si terminal ne supporte pas unicode
    import os
    if os.environ.get("TERM") == "linux":
        ROLE_ASCII = {
            "boot": "[B]",
            "kernel": "[K]",
            "initramfs": "[I]",
            "squashfs": "[S]",
            "modules": "[M]",
            "rootfs": "[R]",
            "overlay": "[O]",
            "python_env": "[P]",
            "efi": "[E]",
            "home": "[H]",
            "archive": "[A]",
            "snapshot": "[@]",
            "data": "[D]",
            "cache": "[C]",
            "log": "[L]",
            "btrfs": "[B]",
            "xfs": "[X]",
        }
        return ROLE_ASCII.get(role, "[?]")
    
    return ROLE_EMOJIS.get(role, "❓")


# ═══════════════════════════════════════════════════════════════════
# SCORING AGRÉGÉ MULTI-SIGNAUX
# ═══════════════════════════════════════════════════════════════════

def compute_aggregate_confidence(signals: dict[str, float]) -> float:
    """
    Agrège plusieurs signaux de détection.
    
    Args:
        signals: dict avec clés:
            - pattern_match: score ROLE_PATTERNS (0.0-1.0)
            - magic_bytes: magic bytes détecté (0.0 ou 1.0)
            - content_scan: scan approfondi (0.0-1.0)
            - partition_type: type partition (0.0-1.0)
    
    Returns:
        Confiance agrégée (0.0-1.0)
    
    Formule:
        confidence = 0.40 × pattern_match
                   + 0.30 × magic_bytes
                   + 0.20 × content_scan
                   + 0.10 × partition_type
    """
    weights = {
        "pattern_match": 0.4,
        "magic_bytes": 0.3,
        "content_scan": 0.2,
        "partition_type": 0.1,
    }
    
    total_weight = 0.0
    weighted_sum = 0.0
    
    for signal_name, confidence in signals.items():
        weight = weights.get(signal_name, 0.0)
        if weight > 0 and 0.0 <= confidence <= 1.0:
            weighted_sum += confidence * weight
            total_weight += weight
    
    if total_weight == 0:
        return 0.0
    
    return weighted_sum / total_weight


# ═══════════════════════════════════════════════════════════════════
# EXEMPLE D'UTILISATION
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    from pathlib import Path
    
    # Test scoring
    test_path = Path("/mnt/boot")
    role, confidence, details = score_patterns(test_path)
    
    print(f"Rôle détecté : {role}")
    print(f"Confiance : {confidence:.2%}")
    print(f"Détails : {details}")
    
    # Test agrégation
    signals = {
        "pattern_match": 0.85,
        "magic_bytes": 1.0,
        "content_scan": 0.90,
    }
    
    final_conf = compute_aggregate_confidence(signals)
    print(f"\nConfiance agrégée : {final_conf:.2%}")
    
    # Liste tous les rôles
    print("\nRôles disponibles (par priorité):")
    for role in list_all_roles():
        info = get_role_info(role)
        emoji = get_role_emoji(role)
        color = get_role_color(role)
        print(f"  {emoji} {role:15s} (prio {info['prio']:2d}) — {info['description']}")
