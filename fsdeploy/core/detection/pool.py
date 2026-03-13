"""
fsdeploy.core.detection.pool
=============================
Détecte et analyse tous les pools ZFS disponibles :
  - Import des pools depuis les disques
  - Topologie RAID complète (mirror, raidz1/2/3, stripe, draid…)
  - Status et santé de chaque vdev et disque
  - Propriétés du pool (compression, ashift, feature flags…)
  - Correspondance disques ↔ chemins physiques (/dev/disk/by-id/)

Aucun nom de pool codé en dur.

Usage :
    detector = PoolDetector(cfg)
    pools = detector.scan()          # liste PoolInfo
    detector.import_pool("tank")     # importer sans mount
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Iterator

from fsdeploy.config import FsDeployConfig


# =============================================================================
# TYPES
# =============================================================================

class VdevType(str, Enum):
    DISK        = "disk"        # disque nu (stripe implicite)
    MIRROR      = "mirror"      # mirror N voies
    RAIDZ1      = "raidz1"      # RAID-Z1 (1 parité)
    RAIDZ2      = "raidz2"      # RAID-Z2 (2 parités)
    RAIDZ3      = "raidz3"      # RAID-Z3 (3 parités)
    DRAID1      = "draid1"      # dRAID-1
    DRAID2      = "draid2"      # dRAID-2
    DRAID3      = "draid3"      # dRAID-3
    SPARE       = "spare"       # hot spare
    CACHE       = "cache"       # L2ARC
    LOG         = "log"         # ZIL/SLOG
    SPECIAL     = "special"     # special allocation class
    STRIPE      = "stripe"      # stripe pur (aucune redondance)
    UNKNOWN     = "unknown"

    @classmethod
    def from_str(cls, s: str) -> "VdevType":
        s = s.strip().lower()
        mapping = {
            "mirror":  cls.MIRROR,
            "raidz":   cls.RAIDZ1,   # alias
            "raidz1":  cls.RAIDZ1,
            "raidz2":  cls.RAIDZ2,
            "raidz3":  cls.RAIDZ3,
            "draid":   cls.DRAID1,
            "draid1":  cls.DRAID1,
            "draid2":  cls.DRAID2,
            "draid3":  cls.DRAID3,
            "spare":   cls.SPARE,
            "cache":   cls.CACHE,
            "log":     cls.LOG,
            "special": cls.SPECIAL,
            "disk":    cls.DISK,
            "stripe":  cls.STRIPE,
        }
        return mapping.get(s, cls.UNKNOWN)

    @property
    def redundant(self) -> bool:
        return self in (
            self.MIRROR,
            self.RAIDZ1, self.RAIDZ2, self.RAIDZ3,
            self.DRAID1, self.DRAID2, self.DRAID3,
        )

    @property
    def parity_count(self) -> int:
        return {
            self.RAIDZ1: 1, self.RAIDZ2: 2, self.RAIDZ3: 3,
            self.DRAID1: 1, self.DRAID2: 2, self.DRAID3: 3,
            self.MIRROR: 0,  # n-1 disques sont la "parité"
        }.get(self, 0)

    def label(self) -> str:
        labels = {
            self.DISK:    "Stripe (aucune redondance)",
            self.STRIPE:  "Stripe (aucune redondance)",
            self.MIRROR:  "Mirror",
            self.RAIDZ1:  "RAID-Z1 (1 disque de parité)",
            self.RAIDZ2:  "RAID-Z2 (2 disques de parité)",
            self.RAIDZ3:  "RAID-Z3 (3 disques de parité)",
            self.DRAID1:  "dRAID-1",
            self.DRAID2:  "dRAID-2",
            self.DRAID3:  "dRAID-3",
            self.SPARE:   "Hot spare",
            self.CACHE:   "Cache L2ARC",
            self.LOG:     "ZIL/SLOG",
            self.SPECIAL: "Special allocation",
        }
        return labels.get(self, "Inconnu")


class VdevState(str, Enum):
    ONLINE      = "ONLINE"
    DEGRADED    = "DEGRADED"
    FAULTED     = "FAULTED"
    OFFLINE     = "OFFLINE"
    UNAVAIL     = "UNAVAIL"
    REMOVED     = "REMOVED"
    UNKNOWN     = "UNKNOWN"

    @classmethod
    def from_str(cls, s: str) -> "VdevState":
        try:
            return cls(s.strip().upper())
        except ValueError:
            return cls.UNKNOWN

    @property
    def healthy(self) -> bool:
        return self == self.ONLINE

    @property
    def icon(self) -> str:
        icons = {
            self.ONLINE:   "✅",
            self.DEGRADED: "⚠️",
            self.FAULTED:  "❌",
            self.OFFLINE:  "⭘",
            self.UNAVAIL:  "❓",
            self.REMOVED:  "🗑",
        }
        return icons.get(self, "❓")


class PoolState(str, Enum):
    ONLINE      = "ONLINE"
    DEGRADED    = "DEGRADED"
    FAULTED     = "FAULTED"
    OFFLINE     = "OFFLINE"
    UNAVAIL     = "UNAVAIL"
    SUSPENDED   = "SUSPENDED"
    UNKNOWN     = "UNKNOWN"

    @classmethod
    def from_str(cls, s: str) -> "PoolState":
        try:
            return cls(s.strip().upper())
        except ValueError:
            return cls.UNKNOWN

    @property
    def healthy(self) -> bool:
        return self == self.ONLINE

    @property
    def icon(self) -> str:
        return {
            self.ONLINE:    "✅",
            self.DEGRADED:  "⚠️",
            self.FAULTED:   "❌",
            self.OFFLINE:   "⭘",
            self.UNAVAIL:   "❓",
            self.SUSPENDED: "⏸",
        }.get(self, "❓")


# =============================================================================
# STRUCTURES DE DONNÉES
# =============================================================================

@dataclass
class DiskInfo:
    """Un disque physique membre d'un vdev."""
    path: str                       # chemin tel que vu par ZFS (/dev/sda, gptid/…)
    by_id: str = ""                 # /dev/disk/by-id/… (résolu si possible)
    state: VdevState = VdevState.UNKNOWN
    read_errors: int = 0
    write_errors: int = 0
    cksum_errors: int = 0
    # Infos physiques (via pyudev si disponible)
    model: str = ""
    serial: str = ""
    size_bytes: int = 0
    rotational: bool = True         # SSD = False
    transport: str = ""             # nvme, sata, sas, usb…
    # Notes (spare, replacing, resilver en cours…)
    notes: list[str] = field(default_factory=list)

    @property
    def short_name(self) -> str:
        """Nom court pour l'affichage."""
        if self.by_id:
            # Préférer le nom by-id sans le préfixe ata-/nvme-
            base = Path(self.by_id).name
            for prefix in ("nvme-", "ata-", "scsi-", "wwn-", "usb-"):
                if base.startswith(prefix):
                    return base[len(prefix):]
            return base
        return Path(self.path).name

    def to_dict(self) -> dict:
        return {
            "path":         self.path,
            "by_id":        self.by_id,
            "state":        self.state.value,
            "healthy":      self.state.healthy,
            "errors":       {
                "read":  self.read_errors,
                "write": self.write_errors,
                "cksum": self.cksum_errors,
            },
            "model":        self.model,
            "serial":       self.serial,
            "size_bytes":   self.size_bytes,
            "rotational":   self.rotational,
            "transport":    self.transport,
            "notes":        self.notes,
        }


@dataclass
class VdevInfo:
    """Un vdev (groupe de disques avec une topologie RAID)."""
    vdev_type: VdevType
    state: VdevState = VdevState.UNKNOWN
    disks: list[DiskInfo] = field(default_factory=list)
    # Pour mirror : nombre de voies
    # Pour raidz  : nombre de disques données (parity déduit)
    width: int = 0
    # Informations de résilver/scrub en cours
    resilver_pct: float = 0.0
    scrub_in_progress: bool = False
    notes: list[str] = field(default_factory=list)

    @property
    def disk_count(self) -> int:
        return len(self.disks)

    @property
    def usable_disks(self) -> int:
        """Disques effectivement utilisables (hors parité mirror)."""
        t = self.vdev_type
        if t == VdevType.MIRROR:
            return 1  # N miroirs = 1 copie utile
        if t in (VdevType.RAIDZ1,):
            return max(0, self.disk_count - 1)
        if t in (VdevType.RAIDZ2,):
            return max(0, self.disk_count - 2)
        if t in (VdevType.RAIDZ3,):
            return max(0, self.disk_count - 3)
        return self.disk_count

    @property
    def fault_tolerance(self) -> str:
        """Décrit combien de disques peuvent tomber sans perte de données."""
        t = self.vdev_type
        if t == VdevType.MIRROR:
            return f"{self.disk_count - 1} disque(s) peuvent tomber"
        if t in (VdevType.RAIDZ1, VdevType.DRAID1):
            return "1 disque peut tomber"
        if t in (VdevType.RAIDZ2, VdevType.DRAID2):
            return "2 disques peuvent tomber"
        if t in (VdevType.RAIDZ3, VdevType.DRAID3):
            return "3 disques peuvent tomber"
        return "aucune redondance"

    @property
    def has_errors(self) -> bool:
        return any(
            d.read_errors + d.write_errors + d.cksum_errors > 0
            for d in self.disks
        )

    def to_dict(self) -> dict:
        return {
            "type":           self.vdev_type.value,
            "type_label":     self.vdev_type.label(),
            "state":          self.state.value,
            "healthy":        self.state.healthy,
            "disk_count":     self.disk_count,
            "usable_disks":   self.usable_disks,
            "fault_tolerance":self.fault_tolerance,
            "has_errors":     self.has_errors,
            "resilver_pct":   self.resilver_pct,
            "disks":          [d.to_dict() for d in self.disks],
            "notes":          self.notes,
        }


@dataclass
class PoolInfo:
    """Informations complètes sur un pool ZFS."""
    name: str
    state: PoolState = PoolState.UNKNOWN
    # Topologie
    data_vdevs: list[VdevInfo] = field(default_factory=list)   # vdevs de données
    cache_vdevs: list[VdevInfo] = field(default_factory=list)  # L2ARC
    log_vdevs: list[VdevInfo] = field(default_factory=list)    # ZIL/SLOG
    spare_vdevs: list[VdevInfo] = field(default_factory=list)  # hot spares
    special_vdevs: list[VdevInfo] = field(default_factory=list)# special

    # Propriétés du pool
    guid: str = ""
    size: str = ""
    alloc: str = ""
    free: str = ""
    frag: str = ""
    cap: str = ""
    health: str = ""
    altroot: str = ""
    ashift: str = ""
    compression: str = ""
    dedup: str = ""
    autotrim: str = ""
    feature_flags: dict[str, str] = field(default_factory=dict)

    # Status global (texte de zpool status)
    status_message: str = ""
    action_message: str = ""
    scan_status: str = ""
    errors: str = ""

    # Importé ou non dans ce run
    imported: bool = False

    @property
    def raid_summary(self) -> str:
        """Résumé lisible de la topologie RAID du pool."""
        if not self.data_vdevs:
            return "Inconnu"
        types = [v.vdev_type for v in self.data_vdevs]
        unique_types = list(dict.fromkeys(types))  # ordre préservé, dédupliqué

        if len(self.data_vdevs) == 1:
            v = self.data_vdevs[0]
            if v.vdev_type in (VdevType.DISK, VdevType.STRIPE):
                return f"Stripe pur ({v.disk_count} disque{'s' if v.disk_count > 1 else ''})"
            if v.vdev_type == VdevType.MIRROR:
                return f"Mirror {v.disk_count} voies"
            return f"{v.vdev_type.value.upper()} ({v.disk_count} disques)"

        # Plusieurs vdevs
        parts = []
        for v in self.data_vdevs:
            if v.vdev_type == VdevType.MIRROR:
                parts.append(f"mirror-{v.disk_count}")
            elif v.vdev_type in (VdevType.RAIDZ1, VdevType.RAIDZ2, VdevType.RAIDZ3):
                parts.append(f"{v.vdev_type.value}({v.disk_count}d)")
            else:
                parts.append(f"{v.vdev_type.value}")
        return " + ".join(parts)

    @property
    def total_disk_count(self) -> int:
        return sum(v.disk_count for v in self.data_vdevs)

    @property
    def all_disks(self) -> list[DiskInfo]:
        disks = []
        for vdevs in (self.data_vdevs, self.cache_vdevs, self.log_vdevs,
                      self.spare_vdevs, self.special_vdevs):
            for v in vdevs:
                disks.extend(v.disks)
        return disks

    @property
    def has_errors(self) -> bool:
        return any(d.has_errors for d in self.data_vdevs)

    @property
    def degraded(self) -> bool:
        return self.state != PoolState.ONLINE or any(
            v.state != VdevState.ONLINE for v in self.data_vdevs
        )

    def to_dict(self) -> dict:
        return {
            "name":         self.name,
            "state":        self.state.value,
            "healthy":      self.state.healthy,
            "imported":     self.imported,
            "guid":         self.guid,
            "size":         self.size,
            "alloc":        self.alloc,
            "free":         self.free,
            "frag":         self.frag,
            "cap":          self.cap,
            "ashift":       self.ashift,
            "compression":  self.compression,
            "dedup":        self.dedup,
            "raid_summary": self.raid_summary,
            "total_disks":  self.total_disk_count,
            "has_errors":   self.has_errors,
            "degraded":     self.degraded,
            "data_vdevs":   [v.to_dict() for v in self.data_vdevs],
            "cache_vdevs":  [v.to_dict() for v in self.cache_vdevs],
            "log_vdevs":    [v.to_dict() for v in self.log_vdevs],
            "spare_vdevs":  [v.to_dict() for v in self.spare_vdevs],
            "status_message": self.status_message,
            "action_message": self.action_message,
            "scan_status":  self.scan_status,
            "errors":       self.errors,
        }


# =============================================================================
# PARSEUR DE zpool status
# =============================================================================

class ZpoolStatusParser:
    """
    Parse la sortie de `zpool status -v <pool>`.
    La sortie est en texte tabulé avec une structure hiérarchique
    indentation-based.

    Exemple de sortie :
        pool: tank
       state: DEGRADED
      status: One or more devices…
      action: Online the device…
        scan: scrub repaired 0B in 00:01:22 with 0 errors on…
      config:

              NAME        STATE     READ WRITE CKSUM
              tank        DEGRADED     0     0     0
                mirror-0  ONLINE       0     0     0
                  sda      ONLINE      0     0     0
                  sdb      OFFLINE     0     0     0
                cache
                  sdc      ONLINE      0     0     0
                log
                  sdd      ONLINE      0     0     0
                spares
                  sde      AVAIL       0     0     0

      errors: No known data errors
    """

    # Section courante dans config:
    _SECTION_KEYWORDS = {"cache", "log", "logs", "spares", "spare", "special", "dedup"}

    def parse(self, raw: str) -> dict:
        """
        Retourne un dict avec toutes les infos extraites.
        """
        result: dict = {
            "name":           "",
            "state":          "UNKNOWN",
            "status_message": "",
            "action_message": "",
            "scan_status":    "",
            "errors":         "",
            "vdevs":          {
                "data":    [],
                "cache":   [],
                "log":     [],
                "spare":   [],
                "special": [],
            },
        }

        lines = raw.splitlines()
        in_config = False
        config_lines: list[str] = []

        # ── Parse des champs hors config ─────────────────────────────────────
        multiline_key = None
        multiline_buf = []

        for line in lines:
            # Détecter le bloc config:
            if re.match(r"^\s*config\s*:", line):
                in_config = True
                continue
            if in_config:
                # Fin du bloc config : ligne commençant par "errors:" ou "status:"
                if re.match(r"^\s*(errors|status|action|scan)\s*:", line):
                    in_config = False
                    # Tomber dans le parsing normal ci-dessous
                else:
                    config_lines.append(line)
                    continue

            # Champs simples
            for field_name, key in [
                ("pool",   "name"),
                ("state",  "state"),
                ("errors", "errors"),
            ]:
                m = re.match(rf"^\s*{field_name}\s*:\s*(.+)", line)
                if m:
                    result[key] = m.group(1).strip()

            # Champs multi-lignes
            m = re.match(r"^\s*(status|action|scan)\s*:\s*(.*)", line)
            if m:
                multiline_key = {
                    "status": "status_message",
                    "action": "action_message",
                    "scan":   "scan_status",
                }[m.group(1)]
                multiline_buf = [m.group(2).strip()]
                continue
            # Suite d'un champ multi-lignes (ligne indentée sans clé)
            if multiline_key and re.match(r"^\s{8}", line) and not re.match(r"^\s+\w+\s*:", line):
                multiline_buf.append(line.strip())
                continue
            if multiline_key:
                result[multiline_key] = " ".join(multiline_buf).strip()
                multiline_key = None
                multiline_buf = []

        if multiline_key:
            result[multiline_key] = " ".join(multiline_buf).strip()

        # ── Parse du bloc config ──────────────────────────────────────────────
        result["vdevs"] = self._parse_config_block(config_lines, result["name"])

        return result

    def _parse_config_block(
        self, lines: list[str], pool_name: str
    ) -> dict[str, list[dict]]:
        """
        Parse le bloc config: de zpool status.
        Retourne {"data": [...], "cache": [...], "log": [...], "spare": [...], "special": [...]}
        """
        vdevs: dict[str, list[dict]] = {
            "data": [], "cache": [], "log": [], "spare": [], "special": [],
        }

        # Supprimer la ligne d'en-tête (NAME STATE READ WRITE CKSUM)
        config_lines = [
            l for l in lines
            if not re.match(r"^\s*NAME\s+STATE\s+READ", l) and l.strip()
        ]

        # Calculer l'indentation de base (pool = niveau 0)
        # On saute les lignes de pool lui-même (indentation minimale)
        base_indent = self._get_base_indent(config_lines, pool_name)

        current_section = "data"
        current_vdev: dict | None = None

        for line in config_lines:
            if not line.strip():
                continue

            indent = len(line) - len(line.lstrip())
            parts  = line.split()
            if not parts:
                continue

            name   = parts[0]
            state  = parts[1] if len(parts) > 1 else "UNKNOWN"
            reads  = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
            writes = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0
            cksum  = int(parts[4]) if len(parts) > 4 and parts[4].isdigit() else 0

            # Le pool lui-même (indentation minimale) → skip
            if name == pool_name or indent == base_indent:
                continue

            # Niveau vdev-group (section : cache, log, spares, special)
            name_lower = name.lower().rstrip(":")
            if name_lower in self._SECTION_KEYWORDS:
                current_section = {
                    "cache":   "cache",
                    "log":     "log",
                    "logs":    "log",
                    "spares":  "spare",
                    "spare":   "spare",
                    "special": "special",
                    "dedup":   "special",
                }.get(name_lower, "data")
                current_vdev = None
                continue

            vdev_type = VdevType.from_str(name.split("-")[0])
            is_vdev_group = vdev_type not in (VdevType.DISK, VdevType.UNKNOWN) \
                            or re.match(r"(mirror|raidz|draid)", name, re.I)

            if is_vdev_group:
                # Nouveau groupe vdev (mirror-0, raidz1-0, etc.)
                current_vdev = {
                    "type":     vdev_type.value,
                    "name":     name,
                    "state":    state,
                    "disks":    [],
                    "notes":    [],
                }
                # Compter les disques → déterminé à la fin
                vdevs[current_section].append(current_vdev)
            else:
                # C'est un disque
                disk = {
                    "path":         name,
                    "state":        state,
                    "read_errors":  reads,
                    "write_errors": writes,
                    "cksum_errors": cksum,
                    "notes":        [],
                }
                # Notes spéciales (spare, replacing…)
                if len(parts) > 5:
                    disk["notes"] = parts[5:]

                if current_vdev is not None:
                    current_vdev["disks"].append(disk)
                else:
                    # Disque nu = stripe implicite
                    vdevs[current_section].append({
                        "type":  VdevType.STRIPE.value,
                        "name":  name,
                        "state": state,
                        "disks": [disk],
                        "notes": [],
                    })

        return vdevs

    def _get_base_indent(self, lines: list[str], pool_name: str) -> int:
        for line in lines:
            if pool_name in line:
                return len(line) - len(line.lstrip())
        # Fallback : indentation minimale des lignes non vides
        indents = [len(l) - len(l.lstrip()) for l in lines if l.strip()]
        return min(indents) if indents else 0


# =============================================================================
# RÉSOLUTION DES DISQUES (/dev/disk/by-id)
# =============================================================================

class DiskResolver:
    """
    Résout les chemins de disques ZFS vers leurs noms by-id.
    Utilise pyudev si disponible, sinon /dev/disk/by-id/*.
    """

    def __init__(self) -> None:
        self._cache: dict[str, str] = {}  # path → by-id
        self._udev_available = self._check_udev()
        self._build_cache()

    def _check_udev(self) -> bool:
        try:
            import pyudev  # noqa: F401
            return True
        except ImportError:
            return False

    def _build_cache(self) -> None:
        """Construit le cache path → by-id depuis /dev/disk/by-id/."""
        by_id = Path("/dev/disk/by-id")
        if not by_id.exists():
            return
        try:
            for link in by_id.iterdir():
                try:
                    target = link.resolve()
                    self._cache[str(target)] = str(link)
                    # Aussi la version courte (sda, nvme0n1…)
                    self._cache[target.name] = str(link)
                except OSError:
                    continue
        except OSError:
            pass

    def resolve(self, path: str) -> str:
        """Retourne le chemin by-id correspondant, ou '' si introuvable."""
        # Essai direct
        if path in self._cache:
            return self._cache[path]
        # Essai avec résolution du chemin complet
        try:
            full = str(Path(path).resolve())
            return self._cache.get(full, "")
        except OSError:
            return ""

    def get_disk_info(self, path: str) -> dict:
        """
        Retourne les infos physiques du disque (taille, modèle, serial, SSD/HDD).
        Utilise pyudev si dispo, sinon /sys/block/.
        """
        info = {
            "model":      "",
            "serial":     "",
            "size_bytes": 0,
            "rotational": True,
            "transport":  "",
        }

        # Nom de bloc (sda, nvme0n1…)
        block_name = Path(path).name.split("p")[0]  # nvme0n1p1 → nvme0n1

        if self._udev_available:
            info.update(self._get_info_udev(path, block_name))
        else:
            info.update(self._get_info_sysfs(block_name))

        return info

    def _get_info_udev(self, path: str, block_name: str) -> dict:
        try:
            import pyudev
            ctx = pyudev.Context()
            # Chercher par chemin de nœud
            for dev in ctx.list_devices(subsystem="block", DEVTYPE="disk"):
                if dev.device_node == path or dev.sys_name == block_name:
                    rotational = dev.attributes.asint("queue/rotational", 1) == 1
                    transport = ""
                    if "nvme" in block_name:
                        transport = "nvme"
                    elif dev.get("ID_BUS"):
                        transport = dev.get("ID_BUS", "")

                    return {
                        "model":      dev.get("ID_MODEL", ""),
                        "serial":     dev.get("ID_SERIAL_SHORT", ""),
                        "size_bytes": self._get_size_sysfs(block_name),
                        "rotational": rotational,
                        "transport":  transport,
                    }
        except Exception:
            pass
        return {}

    def _get_info_sysfs(self, block_name: str) -> dict:
        info: dict = {}
        base = Path(f"/sys/block/{block_name}")
        if not base.exists():
            return info
        try:
            rot = (base / "queue" / "rotational").read_text().strip()
            info["rotational"] = rot == "1"
        except OSError:
            pass
        try:
            size_sectors = int((base / "size").read_text().strip())
            info["size_bytes"] = size_sectors * 512
        except OSError:
            pass
        if "nvme" in block_name:
            info["transport"] = "nvme"
        return info

    def _get_size_sysfs(self, block_name: str) -> int:
        try:
            size_sectors = int(
                Path(f"/sys/block/{block_name}/size").read_text().strip()
            )
            return size_sectors * 512
        except (OSError, ValueError):
            return 0


# =============================================================================
# DÉTECTEUR PRINCIPAL DE POOLS
# =============================================================================

class PoolDetector:
    """
    Scanne, importe et analyse tous les pools ZFS disponibles.

    Usage :
        detector = PoolDetector(cfg)

        # Lister les pools importables (sans les importer)
        available = detector.list_importable()

        # Scanner tous les pools (importés + importables)
        pools = detector.scan(progress_cb=print)

        # Importer un pool spécifique (sans mount)
        detector.import_pool("tank", readonly=True)
    """

    def __init__(self, cfg: FsDeployConfig) -> None:
        self.cfg      = cfg
        self._parser  = ZpoolStatusParser()
        self._resolver = DiskResolver()

    # ── API publique ──────────────────────────────────────────────────────────

    def scan(
        self,
        progress_cb=None,
        import_missing: bool = False,
        readonly: bool = True,
    ) -> list[PoolInfo]:
        """
        Retourne la liste de tous les pools avec leur topologie complète.

        Args:
            progress_cb:    callable(msg) pour le suivi en temps réel
            import_missing: tenter d'importer les pools pas encore importés
            readonly:       importer en lecture seule (recommandé depuis live)
        """
        def log(msg: str) -> None:
            if progress_cb:
                progress_cb(msg)

        log("🔍 Scan des pools ZFS...")

        # ── 1. Pools déjà importés ─────────────────────────────────────────
        imported_names = self._list_imported()
        log(f"   Pools importés : {imported_names or ['aucun']}")

        # ── 2. Pools importables sur les disques ───────────────────────────
        importable = self._list_importable()
        not_imported = [p for p in importable if p not in imported_names]
        if not_imported:
            log(f"   Pools disponibles non importés : {not_imported}")

        if import_missing and not_imported:
            for name in not_imported:
                log(f"   ▶ Import de {name}...")
                ok, msg = self.import_pool(name, readonly=readonly)
                log(f"     {'✅' if ok else '❌'} {msg}")
                if ok:
                    imported_names.append(name)

        # ── 3. Analyser chaque pool importé ───────────────────────────────
        all_pools: list[PoolInfo] = []
        for name in imported_names:
            log(f"   ▶ Analyse de {name}...")
            pool = self._analyze_pool(name)
            pool.imported = True
            all_pools.append(pool)
            log(f"     RAID: {pool.raid_summary}  state={pool.state.value}")

        # ── 4. Pools connus mais pas importés (résumé minimal) ────────────
        for name in not_imported:
            log(f"   ⭘ {name} (non importé)")
            pool = PoolInfo(name=name, state=PoolState.OFFLINE, imported=False)
            all_pools.append(pool)

        # ── 5. Sauvegarder dans la config ─────────────────────────────────
        self._save_to_config(all_pools)

        return all_pools

    def import_pool(
        self,
        name: str,
        readonly: bool = True,
        altroot: str = "",
        no_mount: bool = True,
    ) -> tuple[bool, str]:
        """
        Importe un pool ZFS.

        Args:
            name:     nom du pool
            readonly: importer en lecture seule
            altroot:  chemin alternatif (ex: /mnt pour le live)
            no_mount: ne pas monter les datasets automatiquement
        """
        cmd = ["zpool", "import"]
        if readonly:
            cmd += ["-o", "readonly=on"]
        if no_mount:
            cmd += ["-N"]               # -N = no mount
        if altroot:
            cmd += ["-R", altroot]
        cmd.append(name)

        try:
            r = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30
            )
            if r.returncode == 0:
                return True, f"{name} importé"
            msg = r.stderr.strip() or r.stdout.strip()
            return False, msg
        except subprocess.TimeoutExpired:
            return False, "Timeout lors de l'import"

    def export_pool(self, name: str, force: bool = False) -> tuple[bool, str]:
        """Exporte un pool (unmount propre)."""
        cmd = ["zpool", "export"]
        if force:
            cmd.append("-f")
        cmd.append(name)
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if r.returncode == 0:
                return True, f"{name} exporté"
            return False, r.stderr.strip()
        except subprocess.TimeoutExpired:
            return False, "Timeout"

    def list_importable(self) -> list[str]:
        """Liste les pools disponibles sur les disques (importés ou non)."""
        return self._list_importable()

    # ── Listing ────────────────────────────────────────────────────────────────

    def _list_imported(self) -> list[str]:
        """Retourne les noms des pools actuellement importés."""
        try:
            r = subprocess.run(
                ["zpool", "list", "-H", "-o", "name"],
                capture_output=True, text=True, timeout=10,
            )
            if r.returncode != 0:
                return []
            return [l.strip() for l in r.stdout.splitlines() if l.strip()]
        except subprocess.TimeoutExpired:
            return []

    def _list_importable(self) -> list[str]:
        """
        Retourne tous les pools disponibles sur les disques,
        qu'ils soient importés ou non.
        """
        try:
            r = subprocess.run(
                ["zpool", "import"],
                capture_output=True, text=True, timeout=15,
            )
            names = []
            for line in r.stdout.splitlines():
                m = re.match(r"^\s*pool\s*:\s*(\S+)", line)
                if m:
                    names.append(m.group(1))
            return names
        except subprocess.TimeoutExpired:
            return []

    # ── Analyse d'un pool ─────────────────────────────────────────────────────

    def _analyze_pool(self, name: str) -> PoolInfo:
        """Analyse complète d'un pool importé."""
        pool = PoolInfo(name=name)

        # ── zpool status -v ────────────────────────────────────────────────
        try:
            r = subprocess.run(
                ["zpool", "status", "-v", name],
                capture_output=True, text=True, timeout=15,
            )
            if r.returncode == 0:
                parsed = self._parser.parse(r.stdout)
                pool.state          = PoolState.from_str(parsed.get("state", "UNKNOWN"))
                pool.status_message = parsed.get("status_message", "")
                pool.action_message = parsed.get("action_message", "")
                pool.scan_status    = parsed.get("scan_status", "")
                pool.errors         = parsed.get("errors", "")
                # Construire la topologie vdev
                pool.data_vdevs    = self._build_vdevs(parsed["vdevs"]["data"])
                pool.cache_vdevs   = self._build_vdevs(parsed["vdevs"]["cache"])
                pool.log_vdevs     = self._build_vdevs(parsed["vdevs"]["log"])
                pool.spare_vdevs   = self._build_vdevs(parsed["vdevs"]["spare"])
                pool.special_vdevs = self._build_vdevs(parsed["vdevs"]["special"])
        except subprocess.TimeoutExpired:
            pool.status_message = "Timeout zpool status"

        # ── zpool get all ─────────────────────────────────────────────────
        props = self._get_pool_props(name)
        pool.guid        = props.get("guid", "")
        pool.size        = props.get("size", "")
        pool.alloc       = props.get("allocated", "")
        pool.free        = props.get("free", "")
        pool.frag        = props.get("fragmentation", "")
        pool.cap         = props.get("capacity", "")
        pool.ashift      = props.get("ashift", "")
        pool.compression = props.get("compression", "")
        pool.dedup       = props.get("deduplication", "")
        pool.autotrim    = props.get("autotrim", "")
        pool.altroot     = props.get("altroot", "-")

        return pool

    def _build_vdevs(self, raw_vdevs: list[dict]) -> list[VdevInfo]:
        """Construit des VdevInfo à partir des dicts parsés."""
        vdevs = []
        for rv in raw_vdevs:
            vtype = VdevType.from_str(rv.get("type", "unknown"))
            vdev  = VdevInfo(
                vdev_type = vtype,
                state     = VdevState.from_str(rv.get("state", "UNKNOWN")),
                width     = len(rv.get("disks", [])),
            )
            # Disques
            for rd in rv.get("disks", []):
                path   = rd["path"]
                by_id  = self._resolver.resolve(path)
                dinfo  = self._resolver.get_disk_info(path)
                disk = DiskInfo(
                    path          = path,
                    by_id         = by_id,
                    state         = VdevState.from_str(rd.get("state", "UNKNOWN")),
                    read_errors   = rd.get("read_errors", 0),
                    write_errors  = rd.get("write_errors", 0),
                    cksum_errors  = rd.get("cksum_errors", 0),
                    notes         = rd.get("notes", []),
                    model         = dinfo.get("model", ""),
                    serial        = dinfo.get("serial", ""),
                    size_bytes    = dinfo.get("size_bytes", 0),
                    rotational    = dinfo.get("rotational", True),
                    transport     = dinfo.get("transport", ""),
                )
                vdev.disks.append(disk)

            # Résilver en cours ?
            for note in rv.get("notes", []):
                if "resilver" in note.lower():
                    m = re.search(r"([\d.]+)%", note)
                    if m:
                        vdev.resilver_pct = float(m.group(1))

            vdevs.append(vdev)
        return vdevs

    def _get_pool_props(self, name: str) -> dict[str, str]:
        """Retourne les propriétés d'un pool via zpool get all."""
        props: dict[str, str] = {}
        try:
            r = subprocess.run(
                ["zpool", "get", "-H", "-o", "property,value", "all", name],
                capture_output=True, text=True, timeout=10,
            )
            for line in r.stdout.splitlines():
                parts = line.split("\t", 1)
                if len(parts) == 2:
                    props[parts[0].strip()] = parts[1].strip()
        except subprocess.TimeoutExpired:
            pass
        return props

    # ── Persistance ────────────────────────────────────────────────────────────

    def _save_to_config(self, pools: list[PoolInfo]) -> None:
        """Sauvegarde le résumé des pools dans la config."""
        import json
        summary = {
            "total":    len(pools),
            "imported": [p.name for p in pools if p.imported],
            "pools":    {p.name: p.to_dict() for p in pools},
        }
        self.cfg.set("detection.pools_json", json.dumps(summary))
        # Enregistrer le boot_pool détecté si un seul pool EFI/boot évident
        boot_candidates = [
            p for p in pools
            if p.imported and any(
                "/" not in p.name  # pool racine
                for _ in [None]
            )
        ]
        if boot_candidates:
            # Heuristique : le plus petit pool (souvent boot_pool sur NVMe séparé)
            pass  # sera affiné par DetectionReport
        self.cfg.save()
