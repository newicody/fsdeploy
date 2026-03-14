"""
fsdeploy.core.install.detect
=============================
Détection du système init d'un rootfs par inspection filesystem.

N'exécute AUCUNE commande — examine uniquement les chemins.
Fonctionne donc aussi bien sur un rootfs monté (live) que sur le
système courant (/), ou même un rootfs non-booté.

Ordre de détection (du plus spécifique au plus générique) :

  1. OpenRC   → /sbin/openrc  ou  /etc/openrc  ou  /etc/runlevels
  2. systemd  → /run/systemd/private  ou  /lib/systemd/systemd
               ou  /usr/lib/systemd/systemd
  3. sysvinit → /sbin/init  ET  /etc/inittab
  4. runit    → /sbin/runit  ou  /etc/runit
  5. s6       → /sbin/s6-svscan
  6. unknown  → fallback

Le rootfs peut être :
  - /           (système courant, live ou booté)
  - /mnt/xxx    (rootfs cible monté depuis le live)
  - /mnt/zbm    (rootfs monté par ZFSBootMenu pour inspection)

Usage :
    from fsdeploy.core.install.detect import detect_init_system, InitSystem

    init = detect_init_system(Path("/mnt/gentoo"))
    print(init.name)         # "openrc"
    print(init.label)        # "OpenRC"
    print(init.service_dir)  # Path("/etc/init.d")
    print(init.enable_cmd)   # ["rc-update", "add", "{service}", "default"]
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Sequence


# =============================================================================
# ENUM
# =============================================================================

class InitSystem(str, Enum):
    """Système init détecté dans un rootfs."""

    OPENRC   = "openrc"
    SYSTEMD  = "systemd"
    SYSVINIT = "sysvinit"
    RUNIT    = "runit"
    S6       = "s6"
    UNKNOWN  = "unknown"

    # ── Propriétés pratiques ──────────────────────────────────────────────

    @property
    def label(self) -> str:
        return {
            "openrc":   "OpenRC",
            "systemd":  "systemd",
            "sysvinit": "SysVinit",
            "runit":    "runit",
            "s6":       "s6",
            "unknown":  "Inconnu",
        }[self.value]

    @property
    def service_dir(self) -> Path:
        """Répertoire des scripts de service."""
        return {
            "openrc":   Path("/etc/init.d"),
            "systemd":  Path("/etc/systemd/system"),
            "sysvinit": Path("/etc/init.d"),
            "runit":    Path("/etc/sv"),
            "s6":       Path("/etc/s6/sv"),
            "unknown":  Path("/etc/init.d"),
        }[self.value]

    @property
    def enable_cmd_template(self) -> list[str]:
        """
        Commande pour activer un service (token {service} à remplacer).
        Renvoie [] si pas de commande d'activation connue.
        """
        return {
            "openrc":   ["rc-update", "add", "{service}", "default"],
            "systemd":  ["systemctl", "enable", "{service}"],
            "sysvinit": ["update-rc.d", "{service}", "defaults"],
            "runit":    ["ln", "-s", "/etc/sv/{service}", "/var/service/{service}"],
            "s6":       [],   # activation manuelle via symlinks
            "unknown":  [],
        }[self.value]

    def enable_cmd(self, service: str) -> list[str]:
        """Commande d'activation avec le nom de service substitué."""
        return [
            token.replace("{service}", service)
            for token in self.enable_cmd_template
        ]

    @property
    def disable_cmd_template(self) -> list[str]:
        return {
            "openrc":   ["rc-update", "del", "{service}"],
            "systemd":  ["systemctl", "disable", "{service}"],
            "sysvinit": ["update-rc.d", "{service}", "disable"],
            "runit":    ["rm", "-f", "/var/service/{service}"],
            "s6":       [],
            "unknown":  [],
        }[self.value]

    def disable_cmd(self, service: str) -> list[str]:
        return [
            token.replace("{service}", service)
            for token in self.disable_cmd_template
        ]

    @property
    def supports_chroot_enable(self) -> bool:
        """
        True si la commande d'activation peut être lancée via chroot
        sans démarrer de daemon (elle est purement déclarative).
        """
        return self in (InitSystem.OPENRC, InitSystem.SYSTEMD, InitSystem.SYSVINIT)

    @property
    def unit_extension(self) -> str:
        """Extension des fichiers de service."""
        return {
            "openrc":   "",          # script init.d sans extension
            "systemd":  ".service",
            "sysvinit": "",
            "runit":    "",          # répertoire sv/
            "s6":       "",
            "unknown":  "",
        }[self.value]


# =============================================================================
# RÈGLES DE DÉTECTION
# =============================================================================

@dataclass
class _Rule:
    """
    Règle de détection : l'init est confirmé si TOUTES les preuves
    `must_exist` existent ET qu'AUCUNE des `must_not_exist` n'existe.
    """
    init:          InitSystem
    must_exist:    list[str]             # chemins relatifs à la racine du rootfs
    must_not_exist: list[str] = field(default_factory=list)
    weight:        int = 1               # en cas d'ambiguïté, priorité au plus lourd


# Ordre décroissant de spécificité — le premier qui matche gagne.
_RULES: list[_Rule] = [

    # ── OpenRC ────────────────────────────────────────────────────────────
    # Gentoo, Alpine, Artix-OpenRC, Devuan-OpenRC
    _Rule(
        init=InitSystem.OPENRC,
        must_exist=["sbin/openrc"],
        weight=10,
    ),
    _Rule(
        init=InitSystem.OPENRC,
        must_exist=["etc/openrc"],
        weight=9,
    ),
    _Rule(
        init=InitSystem.OPENRC,
        must_exist=["etc/runlevels", "etc/init.d"],
        must_not_exist=["lib/systemd/systemd", "usr/lib/systemd/systemd"],
        weight=8,
    ),

    # ── systemd ───────────────────────────────────────────────────────────
    # Debian, Ubuntu, Fedora, Arch…
    _Rule(
        init=InitSystem.SYSTEMD,
        must_exist=["lib/systemd/systemd"],
        weight=10,
    ),
    _Rule(
        init=InitSystem.SYSTEMD,
        must_exist=["usr/lib/systemd/systemd"],
        weight=10,
    ),
    _Rule(
        init=InitSystem.SYSTEMD,
        must_exist=["etc/systemd/system"],
        weight=7,
    ),

    # ── runit ─────────────────────────────────────────────────────────────
    # Void Linux, Artix-runit
    _Rule(
        init=InitSystem.RUNIT,
        must_exist=["sbin/runit"],
        weight=10,
    ),
    _Rule(
        init=InitSystem.RUNIT,
        must_exist=["etc/runit"],
        weight=8,
    ),

    # ── s6 ────────────────────────────────────────────────────────────────
    _Rule(
        init=InitSystem.S6,
        must_exist=["sbin/s6-svscan"],
        weight=10,
    ),

    # ── SysVinit ──────────────────────────────────────────────────────────
    # Debian jessie et antérieur, Slackware
    _Rule(
        init=InitSystem.SYSVINIT,
        must_exist=["sbin/init", "etc/inittab"],
        must_not_exist=[
            "sbin/openrc",
            "lib/systemd/systemd",
            "usr/lib/systemd/systemd",
        ],
        weight=6,
    ),
    _Rule(
        init=InitSystem.SYSVINIT,
        must_exist=["etc/init.d", "etc/inittab"],
        must_not_exist=[
            "sbin/openrc",
            "lib/systemd/systemd",
            "usr/lib/systemd/systemd",
        ],
        weight=5,
    ),
]


# =============================================================================
# FONCTION PUBLIQUE
# =============================================================================

def detect_init_system(root: Path | str = Path("/")) -> InitSystem:
    """
    Détecte le système init du rootfs à `root`.

    N'exécute aucune commande — inspection filesystem uniquement.
    Fonctionne sur un rootfs non-booté (live, chroot, ZFSBootMenu).

    Args:
        root: Racine du rootfs à inspecter.
              "/" pour le système courant,
              "/mnt/target" pour un rootfs monté.

    Returns:
        InitSystem enum (OPENRC, SYSTEMD, SYSVINIT, RUNIT, S6 ou UNKNOWN).
    """
    root = Path(root)

    best_init   = InitSystem.UNKNOWN
    best_weight = -1

    for rule in _RULES:
        # Toutes les preuves obligatoires doivent exister
        if not all((root / p).exists() for p in rule.must_exist):
            continue

        # Aucune contre-preuve ne doit exister
        if any((root / p).exists() for p in rule.must_not_exist):
            continue

        if rule.weight > best_weight:
            best_weight = rule.weight
            best_init   = rule.init

    return best_init


def detect_init_system_verbose(root: Path | str = Path("/")) -> dict:
    """
    Version verbose retournant le détail de la détection.
    Utile pour les logs de diagnostic dans l'UI.

    Returns:
        {
            "init":    InitSystem,
            "root":    str,
            "matched": [{"rule_index": int, "init": str, "weight": int,
                         "exists": [...], "missing": [...]}],
            "skipped": [{"rule_index": int, "init": str,
                         "missing_must_exist": [...],
                         "blocked_by": [...]}],
        }
    """
    root = Path(root)
    matched = []
    skipped = []

    for i, rule in enumerate(_RULES):
        missing_must = [p for p in rule.must_exist
                        if not (root / p).exists()]
        blocked_by   = [p for p in rule.must_not_exist
                        if (root / p).exists()]

        if missing_must or blocked_by:
            skipped.append({
                "rule_index":          i,
                "init":                rule.init.value,
                "missing_must_exist":  missing_must,
                "blocked_by":          blocked_by,
            })
        else:
            matched.append({
                "rule_index": i,
                "init":       rule.init.value,
                "weight":     rule.weight,
                "exists":     rule.must_exist,
            })

    # Reprendre le même algo de sélection
    best_init   = InitSystem.UNKNOWN
    best_weight = -1
    for m in matched:
        if m["weight"] > best_weight:
            best_weight = m["weight"]
            best_init   = InitSystem(m["init"])

    return {
        "init":    best_init,
        "root":    str(root),
        "matched": matched,
        "skipped": skipped,
    }
