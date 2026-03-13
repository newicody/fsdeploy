#!/usr/bin/env python3
# =============================================================================
# python-interface.py — ZFSBootMenu Manager (TUI Textual)
#
# Lancé par : zbm-startup via /mnt/python/launch.sh sur TTY1 (/dev/fb0)
# Ou manuellement : python3 /etc/zfsbootmenu/python_interface.py
#
# ─── Fonctionnalités ──────────────────────────────────────────────────────────
#   Écran principal
#     · Liste des systèmes (presets) avec indicateur actif/en-cours
#     · Détail du preset sélectionné
#     · Définir comme système de boot actif (met à jour les symlinks /boot)
#     · Statut stream en temps réel (countdown, running, stopped)
#     · Table des symlinks $BOOT/boot/
#
#   Écran Stream
#     · Démarrer / Arrêter le stream
#     · Annuler le compte à rebours
#     · Modifier la clé stream, résolution, fps, bitrate
#     · Journal ffmpeg en temps réel
#
#   Écran Preset Config
#     · Éditer tous les champs d'un preset (type prepared ou normal)
#     · Régénérer ZFSBootMenu après modification
#     · Ajouter un nouveau preset
#
#   Écran Snapshots
#     · Profils configurables (composants, planning, rétention)
#     · Créer / restaurer / vérifier / archiver / nettoyer
#     · Nommage : <système>_<label-rootfs>_<composants>_<YYYYMMDD-HHMMSS>
#
#   Écran Failsafe (lecture seule)
#
#   Écran Hot-Swap (changement à chaud)
#     · Kernel   : kexec -l <nouveau kernel> + kexec -e (redémarre sans POST)
#     · Modules  : modprobe / mount nouveau modules.sfs sur /mnt/modloop
#     · Rootfs   : change le symlink rootfs.sfs + kexec pour appliquer
#     · Liste les kernels/modules/rootfs disponibles dans /boot/images/
# =============================================================================

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import uuid
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Generator

try:
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.coordinate import Coordinate
    from textual.screen import Screen
    from textual.widgets import (
        Button, Checkbox, DataTable, Footer, Header,
        Input, Label, ListItem, ListView, Log,
        Select, Static,
    )
    from textual.containers import Horizontal, Vertical, ScrollableContainer
    from textual import on, work
except ImportError:
    print("Textual non installé : pip install textual")
    sys.exit(1)


# =============================================================================
# CONSTANTES
# =============================================================================
# Point de montage de boot_pool
# Sur Debian live : /mnt/zbm/boot  |  Système réel : /boot (legacy, mountpoint=legacy ZFS)
# BOOT est résolu dynamiquement par BootPoolLocator.find() — défini plus bas.
# Pour utiliser BOOT dans ce module : appeler get_boot() ou accéder à BOOT après
# que le module soit entièrement chargé (les constantes dérivées sont recalculées).
# 
# ATTENTION : BootPoolLocator est défini après ce bloc.
# On utilise donc un _lazy_boot() qui appelle BootPoolLocator au runtime.
# Points de montage canoniques — DOIT correspondre à mounts.sh
# Live deploy  : boot_pool → /mnt/zbm/boot   (altroot=/mnt/zbm, cohérent)
# Système réel : boot_pool → /boot           (installé, mountpoint=legacy)
_ZBM_LIVE_ROOT = Path("/mnt/zbm/boot")  # Live deploy (= ZBM_BOOT dans mounts.sh)
_ZBM_LIVE_OLD  = Path("/mnt/zbm-live")  # Ancien chemin (compat migration → /mnt/zbm/boot)
_ZBM_REAL_ROOT = Path("/boot")          # Système réel installé

def _ensure_images_mounted(boot: Path) -> None:
    """Monte boot_pool/images si le dataset existe et n'est pas encore monté.
    boot_pool/images est un dataset enfant ZFS — zpool import -N ne le monte
    pas automatiquement, il faut 'zfs mount boot_pool/images' explicite.
    """
    import subprocess
    images_mp = boot / "images"
    # Vérifier si déjà monté
    try:
        result = subprocess.run(
            ["mountpoint", "-q", str(images_mp)],
            capture_output=True, timeout=2
        )
        if result.returncode == 0:
            return  # déjà monté
    except Exception:
        pass
    # Vérifier si le dataset existe
    try:
        r = subprocess.run(
            ["zfs", "list", "boot_pool/images"],
            capture_output=True, timeout=3
        )
        if r.returncode != 0:
            return  # dataset absent — premier déploiement
    except Exception:
        return
    # Monter
    try:
        images_mp.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["zfs", "mount", "boot_pool/images"],
            capture_output=True, timeout=5
        )
    except Exception:
        pass


def _boot_path() -> Path:
    """Retourne le chemin réel de boot_pool, résolu au premier appel.
    Tente aussi de monter boot_pool/images si nécessaire.
    """
    import subprocess
    # 1. Source de vérité : zfs mount → trouver boot_pool
    try:
        out = subprocess.check_output(["zfs", "mount"], text=True, stderr=subprocess.DEVNULL)
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[0] == "boot_pool":
                boot = Path(parts[1])
                _ensure_images_mounted(boot)
                return boot
    except Exception:
        pass
    # 2. /mnt/zbm/boot est monté (live deploy canonical) ?
    for _live in (_ZBM_LIVE_ROOT, _ZBM_LIVE_OLD):
        try:
            r = subprocess.run(
                ["mountpoint", "-q", str(_live)],
                capture_output=True, timeout=2
            )
            if r.returncode == 0:
                _ensure_images_mounted(_live)
                return _live
        except Exception:
            pass
    # 3. /boot est boot_pool (système réel installé) ?
    try:
        r = subprocess.run(
            ["findmnt", "-n", "-o", "SOURCE", "/boot"],
            capture_output=True, text=True, timeout=2
        )
        if "boot_pool" in r.stdout:
            _ensure_images_mounted(_ZBM_REAL_ROOT)
            return _ZBM_REAL_ROOT
    except Exception:
        pass
    # 4. Fallback : /mnt/zbm/boot (live — pas encore monté, sera tenté par mount_temp)
    return _ZBM_LIVE_ROOT


# BOOT est recalculé une fois au chargement du module.
# Tout code qui s'exécute après le chargement initial verra la valeur correcte.
# Les classes/méthodes appelées au runtime utilisent get_boot() pour être sûres.
BOOT = _boot_path()
IMAGES_DIR    = BOOT / "images"
PRESETS_DIR   = BOOT / "presets"
SNAPSHOTS_DIR = BOOT / "snapshots"
PROFILES_FILE = SNAPSHOTS_DIR / "profiles.json"
FAILSAFE_DIR  = BOOT / "images" / "failsafe"  # recalculé si BOOT change
CURRENT_SYS   = Path("/run/zbm-current-system")
STREAM_STATE  = Path("/run/zbm-stream-state")
STREAM_CD     = Path("/run/zbm-stream-countdown")
STREAM_PID    = Path("/run/zbm-stream.pid")
ZBM_LOG       = Path("/var/log/zbm-startup.log")

# Symlinks actifs dans $BOOT/boot/ — ZBM monte boot_pool comme BE et cherche
# <BE_root>/boot/vmlinuz. boot_pool étant le BE, ses symlinks sont dans $BOOT/boot/.
# BOOT = /mnt/zbm/boot sur live, /boot sur système installé.
# Symlinks = $BOOT/boot/vmlinuz → ../images/kernels/kernel-<label>-<date> (relatif)
# Noms des symlinks dans $BOOT/boot/
ACTIVE_SYMLINKS = {
    "vmlinuz":    "kernel",
    "initrd.img": "initramfs",
    "modules.sfs":"modules",
    "rootfs.sfs": "rootfs",
}
# Répertoire contenant les symlinks ZBM (boot_pool/boot/)
# Calculé au runtime car BOOT peut changer
def _links_dir() -> Path:
    """Retourne $BOOT/boot/ — répertoire des symlinks actifs ZBM."""
    return BOOT / "boot"

FAILSAFE_SYMLINKS = [
    "vmlinuz.failsafe", "initrd.failsafe.img",
    "modules.failsafe.sfs", "rootfs.failsafe.sfs",
]
COMPONENTS = {
    "ovl": "Overlay upper (diff rootfs)",
    "var": "Var  — /var",
    "log": "Log  — /var/log",
    "tmp": "Tmp  — /tmp",
}
SCHEDULES = ["none", "daily", "weekly", "monthly"]
STREAM_RESOLUTIONS = ["1920x1080", "1280x720", "2560x1440"]

# Sous-répertoires images par type
IMAGE_DIRS: dict[str, str] = {
    "kernel":    "kernels",
    "initramfs": "initramfs",
    "modules":   "modules",
    "rootfs":    "rootfs",
    "python":    "startup",
    "failsafe":  "failsafe",
}

# Types d'init reconnus
INIT_TYPES = {
    "zbm":        "ZBM complet (squashfs + overlay + Python TUI + stream)",
    "zbm-stream": "ZBM stream seul (pas de TUI Python)",
    "minimal":    "Init natif du noyau (boot direct rootfs)",
    "custom":     "Init personnalisé",
}

# Types de presets
PRESET_TYPES = {
    "prepared": "Boot complet avec Python TUI et stream",
    "normal":   "Boot système standard",
    "stream":   "Boot optimisé flux vidéo",
    "minimal":  "Boot minimal natif (pas d'overlay)",
    "failsafe": "Failsafe protégé",
}
IMAGE_EXTS: dict[str, str] = {
    "kernel": "", "initramfs": ".img",
    "modules": ".sfs", "rootfs": ".sfs", "python": ".sfs",
}


# config.sh : cherché dans /etc/zfsbootmenu/ ou à la racine de boot_pool
CONFIG_SH      = Path("/etc/zfsbootmenu/config.sh")
CONFIG_SH_BOOT = _boot_path() / "config.sh"  # résolu au chargement


def available_systems() -> list[str]:
    """
    Retourne la liste des systèmes depuis config.sh (SYSTEMS=(...)).
    Sources par ordre de priorité :
      1. /etc/zfsbootmenu/config.sh  (copie installée)
      2. /boot/config.sh             (fallback boot_pool)
      3. Presets JSON dans /boot/presets/*.json (fallback dynamique)
      4. ["systeme1"]                (dernier recours)
    """
    # Chercher config.sh dans /etc/zfsbootmenu/ ou dans boot_pool
    _bp = _boot_path()
    for cfg in [CONFIG_SH, _bp / "config.sh", CONFIG_SH_BOOT]:
        if cfg.exists():
            try:
                cmd = f"source {cfg} 2>/dev/null; printf '%s\\n' \"${{SYSTEMS[@]:-}}\"" 
                ok, out = run(["bash", "-c", cmd])
                systems = [s.strip() for s in out.splitlines() if s.strip()]
                if systems:
                    return systems
            except Exception:
                pass
                pass

    # Fallback : lire les presets (zbm_system dans la cmdline ou name du preset)
    systems: list[str] = []
    if PRESETS_DIR.exists():
        for pf in sorted(PRESETS_DIR.glob("*.json")):
            try:
                d = json.loads(pf.read_text())
                name = d.get("name", "")
                if name and name not in ("initial", "failsafe") and name not in systems:
                    systems.append(name)
            except Exception:
                pass
    return systems if systems else ["systeme1"]


# =============================================================================
# HELPERS
# =============================================================================

def run(cmd: list[str], timeout: int = 120) -> tuple[bool, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0, (r.stdout + r.stderr).strip()
    except Exception as e:
        return False, str(e)

def human_size(n: float) -> str:
    for u in ("B","KB","MB","GB","TB"):
        if n < 1024: return f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} TB"

def dir_size(p: Path) -> str:
    try:
        return human_size(sum(f.stat().st_size for f in p.rglob("*") if f.is_file()))
    except: return "?"

def md5file(p: Path) -> str:
    try: return hashlib.md5(p.read_bytes()).hexdigest()
    except: return ""

def readlink(p: Path) -> str:
    try: return os.readlink(p)
    except: return "—"

def dataset_exists(ds: str) -> bool:
    ok, _ = run(["zfs","list",ds]); return ok

def current_system() -> str:
    try: return CURRENT_SYS.read_text().strip()
    except: return ""

def stream_state() -> str:
    try: return STREAM_STATE.read_text().strip()
    except: return "unknown"

def stream_countdown() -> int:
    try: return int(STREAM_CD.read_text().strip())
    except: return -1


# =============================================================================
# NAMING HELPER — Convention de nommage des images
# Miroir Python de lib/naming.sh
# <type>-<system>-<label>-<YYYYMMDD>[.ext]
# python-<ver>-<YYYYMMDD>.sfs
# =============================================================================

@dataclass
class ImageInfo:
    """Représente une image décodée selon la convention de nommage."""
    path:   Path
    type_:  str   # kernel | initramfs | modules | rootfs | python
    system: str   # systeme1 | systeme2 | failsafe | "" (pour python)
    label:  str   # ex: gentoo-6.19 | 3.11
    date:   str   # YYYYMMDD
    ext:    str   # .img | .sfs | ""

    @property
    def set_key(self) -> str:
        """Clé d'ensemble : system/label/date"""
        return f"{self.system}/{self.label}/{self.date}"

    @property
    def filename(self) -> str:
        return self.path.name


class NamingHelper:
    """Convention de nommage unifiée pour toutes les images /boot/images/."""

    KNOWN_TYPES = ("kernel", "initramfs", "modules", "rootfs", "python")
    EXTS = {"kernel": "", "initramfs": ".img", "modules": ".sfs",
            "rootfs": ".sfs", "python": ".sfs"}

    @classmethod
    def image_dir(cls, type_: str, system: str = "") -> Path:
        if system == "failsafe" or type_ == "failsafe":
            return BOOT / "images" / "failsafe"
        return BOOT / "images" / IMAGE_DIRS.get(type_, type_)

    @classmethod
    def stem(cls, type_: str, system: str, label: str,
             date: str | None = None) -> str:
        """Construit le nom de fichier (avec extension).
        
        IMPORTANT :
          kernel / initramfs / modules → PAS de champ system dans le nom
          rootfs seulement → rootfs-<system>-<label>-<date>.sfs
          Le rootfs NE contient NI kernel NI modules (jamais).
        """
        d = date or datetime.now().strftime("%Y%m%d")
        lbl = re.sub(r'[\s/_]', '-', label)
        lbl = re.sub(r'[^a-zA-Z0-9.\-]', '', lbl)
        ext = cls.EXTS.get(type_, "")
        if type_ == "python":
            return f"python-{lbl}-{d}{ext}"
        elif type_ == "rootfs":
            return f"rootfs-{system}-{lbl}-{d}{ext}"
        elif type_ in ("kernel", "initramfs", "modules"):
            if system == "failsafe":
                return f"{type_}-failsafe-{lbl}-{d}{ext}"
            return f"{type_}-{lbl}-{d}{ext}"
        return f"{type_}-{system}-{lbl}-{d}{ext}"

    @classmethod
    def path(cls, type_: str, system: str, label: str,
             date: str | None = None) -> Path:
        return cls.image_dir(type_, system) / cls.stem(type_, system, label, date)

    @classmethod
    def parse(cls, p: Path | str) -> ImageInfo | None:
        """
        Décode un nom de fichier selon la convention.
        Retourne None si non conforme.
        """
        name = Path(p).name
        # Extension
        ext = ""
        stem = name
        for e in (".img", ".sfs"):
            if name.endswith(e):
                ext = e; stem = name[:-len(e)]; break

        # Type
        type_ = ""
        for t in cls.KNOWN_TYPES:
            if stem.startswith(t + "-"):
                type_ = t; stem = stem[len(t)+1:]; break
        if not type_:
            return None

        # Date = 8 derniers chiffres
        if len(stem) < 9 or not re.match(r'\d{8}$', stem[-8:]):
            return None
        date = stem[-8:]
        rest = stem[:-9]  # retirer -YYYYMMDD

        if type_ == "python":
            system, label = "", rest
        elif type_ == "rootfs":
            # rootfs-<system>-<label>-<date>
            parts = rest.split("-", 1)
            if len(parts) < 2:
                return None
            system, label = parts[0], parts[1]
        elif type_ in ("kernel", "initramfs", "modules"):
            # kernel/initramfs/modules-[failsafe-]<label>-<date> — PAS de system
            if rest.startswith("failsafe-"):
                system = "failsafe"
                label = rest[len("failsafe-"):]
            else:
                system = ""
                label = rest
        else:
            system, label = "", rest

        if not label:
            return None

        return ImageInfo(path=Path(p), type_=type_, system=system,
                         label=label, date=date, ext=ext)

    @classmethod
    def list_images(cls, type_: str | None = None) -> list[ImageInfo]:
        """Liste toutes les images connues avec parsing."""
        result: list[ImageInfo] = []
        dirs = [BOOT / "images" / d for d in IMAGE_DIRS.values()]
        seen = set()
        for d in dirs:
            if d in seen or not d.exists(): continue
            seen.add(d)
            for f in sorted(d.iterdir()):
                if not f.is_file(): continue
                img = cls.parse(f)
                if img and (type_ is None or img.type_ == type_):
                    result.append(img)
        return result

    @classmethod
    def list_sets(cls) -> dict[str, list[ImageInfo]]:
        """
        Retourne les groupes d'images disponibles.
        
        Kernel/initramfs/modules sont INDÉPENDANTS → groupés par label+date
        Rootfs sont INDÉPENDANTS → listés séparément
        """
        sets: dict[str, list[ImageInfo]] = {}
        for img in cls.list_images():
            if img.type_ == "python":
                continue
            if img.type_ == "rootfs":
                key = f"rootfs/{img.system}/{img.label}/{img.date}"
            else:
                # kernel/initramfs/modules : pas de system dans la clé
                key = f"{img.type_}/{img.label}/{img.date}"
            sets.setdefault(key, []).append(img)
        return sets

    @classmethod
    def list_boot_combos(cls) -> list[dict]:
        """
        Liste les combinaisons kernel+initramfs disponibles.
        Les modules et rootfs sont indépendants et listés séparément.
        Retourne: [{kernel_label, initramfs_label, date, has_modules}, ...]
        """
        kernels: dict[str, str] = {}   # date -> label
        initramfs_by_date: dict[str, list[str]] = {}  # date -> [labels]
        modules_by_date: set[str] = set()  # dates où des modules existent

        kdir = BOOT / "images" / "kernels"
        idir = BOOT / "images" / "initramfs"
        mdir = BOOT / "images" / "modules"

        if kdir.exists():
            for f in kdir.glob("kernel-*"):
                if f.suffix in (".meta",) or f.name.endswith(".meta"):
                    continue
                info = cls.parse(f)
                if info and info.system != "failsafe":
                    kernels[info.date + ":" + info.label] = info.label

        if idir.exists():
            for f in idir.glob("initramfs-*.img"):
                if f.name.endswith(".meta"):
                    continue
                info = cls.parse(f)
                if info and info.system != "failsafe":
                    initramfs_by_date.setdefault(info.date, []).append(info.label)

        if mdir.exists():
            for f in mdir.glob("modules-*.sfs"):
                if f.name.endswith(".meta"):
                    continue
                info = cls.parse(f)
                if info and info.system != "failsafe":
                    modules_by_date.add(info.date)

        combos = []
        for key, klabel in kernels.items():
            date = key.split(":")[0]
            inits = initramfs_by_date.get(date, [])
            has_mod = date in modules_by_date
            if inits:
                for ilabel in inits:
                    combos.append({
                        "kernel_label": klabel,
                        "initramfs_label": ilabel,
                        "date": date,
                        "has_modules": has_mod,
                    })
            else:
                combos.append({
                    "kernel_label": klabel,
                    "initramfs_label": None,
                    "date": date,
                    "has_modules": has_mod,
                })
        return sorted(combos, key=lambda x: x["date"], reverse=True)

    @classmethod
    def set_complete(cls, kernel_label: str, date: str,
                     require_modules: bool = False,
                     require_rootfs: bool = False,
                     rootfs_system: str = "", rootfs_label: str = "") -> bool:
        """Vérifie qu'un ensemble de boot minimal est présent.
        
        Minimal requis : kernel + au moins un initramfs de la même date.
        Modules et rootfs sont optionnels selon le type de preset.
        """
        k = BOOT / "images" / "kernels" / cls.stem("kernel", "", kernel_label, date)
        if not k.exists():
            return False
        # Chercher un initramfs à cette date
        idir = BOOT / "images" / "initramfs"
        has_init = any(
            f.name.endswith(f"-{date}.img")
            for f in idir.glob(f"initramfs-*-{date}.img")
        ) if idir.exists() else False
        if not has_init:
            return False
        if require_modules:
            mdir = BOOT / "images" / "modules"
            if not (mdir / cls.stem("modules", "", kernel_label, date)).exists():
                return False
        if require_rootfs and rootfs_system and rootfs_label:
            rdir = BOOT / "images" / "rootfs"
            if not (rdir / cls.stem("rootfs", rootfs_system, rootfs_label, date)).exists():
                return False
        return True

    @classmethod
    def latest(cls, type_: str, system: str, label: str) -> Path | None:
        """Retourne le fichier le plus récent pour un type/system/label."""
        candidates = [
            img for img in cls.list_images(type_)
            if img.system == system and img.label == label
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda i: i.date).path

    @classmethod
    def active_symlinks(cls, kernel_label: str, initramfs_label: str, date: str,
                        modules_label: str | None = None,
                        rootfs_system: str = "", rootfs_label: str = "") -> dict[str, str]:
        """Retourne {link_name: target_relative} pour les symlinks actifs.
        
        kernel/initramfs/modules : PAS de system dans le chemin
        rootfs : rootfs-<system>-<label>-<date>.sfs
        """
        links: dict[str, str] = {
            "vmlinuz":    f"images/kernels/{cls.stem('kernel', '', kernel_label, date)}",
            "initrd.img": f"images/initramfs/{cls.stem('initramfs', '', initramfs_label, date)}",
        }
        mlbl = modules_label or kernel_label
        mpath = BOOT / "images" / "modules" / cls.stem("modules", "", mlbl, date)
        if mpath.exists():
            links["modules.sfs"] = f"images/modules/{cls.stem('modules', '', mlbl, date)}"
        if rootfs_system and rootfs_label:
            links["rootfs.sfs"] = f"images/rootfs/{cls.stem('rootfs', rootfs_system, rootfs_label, date)}"
        return links

    @classmethod
    def failsafe_symlinks(cls, label: str, date: str) -> dict[str, str]:
        """Retourne {link_name: target_relative} pour les 4 symlinks failsafe."""
        return {
            "vmlinuz.failsafe":    f"images/failsafe/{cls.stem('kernel',    'failsafe', label, date)}",
            "initrd.failsafe.img": f"images/failsafe/{cls.stem('initramfs', 'failsafe', label, date)}",
            "modules.failsafe.sfs":f"images/failsafe/{cls.stem('modules',   'failsafe', label, date)}",
            "rootfs.failsafe.sfs": f"images/failsafe/{cls.stem('rootfs',    'failsafe', label, date)}",
        }

    @classmethod
    def meta_path(cls, img: Path) -> Path:
        """Chemin du sidecar .meta pour une image."""
        return Path(str(img) + ".meta")

    @classmethod
    def read_meta(cls, img: Path) -> dict:
        """Lit le sidecar JSON .meta. Retourne {} si absent."""
        mp = cls.meta_path(img)
        if not mp.exists():
            return {}
        try:
            return json.loads(mp.read_text())
        except Exception:
            return {}

    @classmethod
    def list_complete_sets(cls) -> list[tuple[str, str, str]]:
        """Ensembles complets (4 types) triés par date décroissante."""
        result = []
        for key, imgs in cls.list_sets().items():
            types_present = {i.type_ for i in imgs}
            if {"kernel","initramfs","modules","rootfs"}.issubset(types_present):
                parts = key.split("/", 2)
                if len(parts) == 3:
                    result.append((parts[0], parts[1], parts[2]))
        return sorted(result, key=lambda x: x[2], reverse=True)

    @classmethod
    def failsafe_meta(cls) -> dict | None:
        """Lit le sidecar .meta JSON le plus récent du failsafe, ou le legacy."""
        if not FAILSAFE_DIR.exists():
            return None
        metas = sorted(FAILSAFE_DIR.glob("*.meta"), reverse=True)
        for m in metas:
            try:
                data = json.loads(m.read_text())
                data["_meta_file"] = str(m)
                return data
            except Exception:
                continue
        legacy = BOOT / "images" / "failsafe" / "failsafe.meta"
        if legacy.exists():
            result: dict[str, str] = {}
            for line in legacy.read_text().splitlines():
                if "=" in line and not line.startswith("#"):
                    k, _, v = line.partition("=")
                    result[k.strip()] = v.strip()
            result["_meta_file"] = str(legacy)
            return result
        return None


# =============================================================================
# DEPLOY MANAGERS — Fonctions de déploiement codées en Python indépendamment
# des scripts bash. Miroir complet de lib/*.sh avec accès direct au système.
# =============================================================================

# ---------------------------------------------------------------------------
# ConfigManager — Miroir de deploy/config.sh
# Lit/écrit config.sh (pure ASCII key="value") et expose toutes les variables.
# ---------------------------------------------------------------------------
class ConfigManager:
    """Lecture et écriture de deploy/config.sh.
    Indépendant de tout script bash — parse le fichier directement.
    """

    # Chemins candidats pour config.sh
    CONFIG_PATHS = [
        Path("/etc/zfsbootmenu/deploy/config.sh"),
        Path("/mnt/zbm/boot/config.sh"),    # live deploy (= ZBM_BOOT)
        Path("/mnt/zbm-live/config.sh"),    # compat ancien chemin (migration)
        Path("/etc/zfsbootmenu/config.sh"),
    ]
    # Ajout du chemin relatif depuis python-interface.py si lancé depuis /boot
    _EXTRA_PATHS: list[Path] = []

    def __init__(self) -> None:
        self._path: Path | None = None
        self._data: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        """Cherche et parse config.sh."""
        candidates = list(self.CONFIG_PATHS) + self._EXTRA_PATHS
        # Chercher aussi depuis /boot/deploy/config.sh
        boot = BootPoolLocator.find()
        if boot:
            candidates += [boot / "deploy" / "config.sh"]
        candidates += [Path("/mnt/zbm/boot/deploy/config.sh"), Path("/mnt/zbm/boot/config.sh"),
                Path("/mnt/zbm-live/deploy/config.sh"),  # compat ancien chemin
                Path("/mnt/zbm-live/config.sh")]          # compat ancien chemin
        for p in candidates:
            if p.exists():
                self._path = p
                self._parse(p)
                return

    def _parse(self, path: Path) -> None:
        """Parse les lignes KEY="val" ou KEY=val d'un fichier bash."""
        self._data = {}
        for line in path.read_text(errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, rest = line.partition("=")
            key = key.strip()
            # Enlever les guillemets
            val = rest.strip().strip('"').strip("'")
            self._data[key] = val

    def get(self, key: str, default: str = "") -> str:
        return self._data.get(key, default)

    def get_systems(self) -> list[str]:
        """Retourne SYSTEMS=(...) comme liste Python."""
        if self._path is None:
            return ["systeme1"]
        # Parser SYSTEMS=("a" "b" ...) via bash dans un sous-shell
        try:
            cmd = f'source "{self._path}" 2>/dev/null; printf "%s\\n" "${{SYSTEMS[@]:-}}"'
            ok2, out = run(["bash", "-c", cmd])
            if ok2:
                syslist = [s.strip() for s in out.splitlines() if s.strip()]
                if syslist:
                    return syslist
        except Exception:
            pass
        return [self._data.get("SYSTEMS", "systeme1").strip('()"\' ')]

    def get_path(self) -> Path | None:
        return self._path

    def set(self, key: str, value: str) -> bool:
        """Met à jour une valeur dans config.sh (sed -i)."""
        if self._path is None:
            return False
        try:
            text = self._path.read_text(errors="replace")
            import re as _re
            pattern = rf'^{_re.escape(key)}=.*$'
            new_line = f'{key}="{value}"'
            if _re.search(pattern, text, _re.MULTILINE):
                text = _re.sub(pattern, new_line, text, flags=_re.MULTILINE)
            else:
                text += f'\n{new_line}\n'
            self._path.write_text(text)
            self._data[key] = value
            return True
        except Exception:
            return False

    def reload(self) -> None:
        if self._path:
            self._parse(self._path)

    @property
    def path_str(self) -> str:
        return str(self._path) if self._path else "(non trouvé)"

    @property
    def kernel_label(self) -> str:
        return self._data.get("KERNEL_LABEL", "")

    @property
    def kernel_ver(self) -> str:
        return self._data.get("KERNEL_VER", "")

    @property
    def init_type(self) -> str:
        return self._data.get("INIT_TYPE", "zbm")

    @property
    def rootfs_label(self) -> str:
        return self._data.get("ROOTFS_LABEL", "gentoo")

    @property
    def rootfs_src(self) -> str:
        return self._data.get("ROOTFS_SRC", "auto")

    @property
    def nvme_a(self) -> str:
        return self._data.get("NVME_A", "")

    @property
    def nvme_b(self) -> str:
        return self._data.get("NVME_B", "")

    @property
    def efi_part(self) -> str:
        return self._data.get("EFI_PART", "")

    @property
    def boot_pool_part(self) -> str:
        return self._data.get("BOOT_POOL_PART", "")


# ---------------------------------------------------------------------------
# BootPoolLocator — Localise boot_pool dynamiquement (miroir de la logique
# partagée kernel.sh / initramfs.sh / presets.sh)
# ---------------------------------------------------------------------------
class BootPoolLocator:
    """Localise le point de montage de boot_pool.
    Ordre : zfs mount → chemin statique /boot → import temporaire.
    """

    @staticmethod
    def find() -> "Path | None":
        """Retourne le mountpoint de boot_pool ou None.
        Délègue à _boot_path() qui gère live vs système réel.
        Tente de monter boot_pool/images si nécessaire.
        Retourne None seulement si boot_pool n'est pas du tout accessible.
        """
        import subprocess
        boot = _boot_path()
        try:
            r = subprocess.run(["mountpoint", "-q", str(boot)],
                               capture_output=True, timeout=2)
            if r.returncode == 0:
                # boot_pool monté — s'assurer que /images est aussi là
                _ensure_images_mounted(boot)
                return boot
        except Exception:
            pass
        # Vérifier via zfs mount (source de vérité la plus fiable)
        try:
            out = subprocess.check_output(["zfs", "mount"], text=True,
                                          stderr=subprocess.DEVNULL)
            for line in out.splitlines():
                parts = line.split()
                if len(parts) >= 2 and parts[0] == "boot_pool":
                    b = Path(parts[1])
                    _ensure_images_mounted(b)
                    return b
        except Exception:
            pass
        return None

    @staticmethod
    def mount_temp() -> "tuple[Path | None, bool]":
        """Monte boot_pool sur /mnt/zbm/boot (= ZBM_BOOT) si pas déjà monté.
        Monte aussi boot_pool/images (dataset enfant, nécessite un montage séparé).
        Sur Debian live /boot est occupé — point de montage fixe.
        Retourne (mountpoint, was_mounted_by_us).
        """
        existing = BootPoolLocator.find()
        if existing:
            _ensure_images_mounted(existing)
            return existing, False
        # Importer si nécessaire
        run(["zpool", "import", "-N", "boot_pool"])
        # Monter sur le chemin canonique live (= ZBM_BOOT = /mnt/zbm/boot)
        mnt = _ZBM_LIVE_ROOT
        mnt.mkdir(parents=True, exist_ok=True)
        ok2, _ = run(["mount", "-t", "zfs", "boot_pool", str(mnt)])
        if ok2:
            _ensure_images_mounted(mnt)
            return mnt, True
        return None, False

    @staticmethod
    def unmount_temp(path: Path) -> None:
        """Démonte boot_pool (et boot_pool/images en premier — enfant ZFS)."""
        import subprocess
        # Démonter boot_pool/images AVANT boot_pool
        try:
            subprocess.run(["zfs", "unmount", "boot_pool/images"],
                           capture_output=True, timeout=5)
        except Exception:
            pass
        ok2, _ = run(["umount", str(path)])
        if ok2:
            try:
                (path / "images").rmdir()
            except Exception:
                pass
            try:
                path.rmdir()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# KernelScanner — Scan des kernels dans boot_pool
# Miroir Python de zbm_select_kernel() de lib/naming.sh
# ---------------------------------------------------------------------------
@dataclass
class KernelEntry:
    """Un kernel installé dans boot_pool avec ses métadonnées."""
    path:       Path
    label:      str
    date:       str
    kver:       str       # depuis le .meta — jamais uname -r
    size_bytes: int
    has_modules: bool
    modules_path: Path | None
    modules_size: int
    is_active:  bool      # = symlink vmlinuz pointe ici
    meta:       dict      # contenu brut du .meta

    @property
    def filename(self) -> str:
        return self.path.name

    @property
    def size_human(self) -> str:
        return human_size(self.size_bytes)

    @property
    def modules_size_human(self) -> str:
        return human_size(self.modules_size) if self.modules_size else "—"

    @property
    def age_days(self) -> int:
        try:
            from datetime import datetime
            d = datetime.strptime(self.date, "%Y%m%d")
            return (datetime.now() - d).days
        except Exception:
            return -1

    @property
    def date_display(self) -> str:
        try:
            from datetime import datetime
            d = datetime.strptime(self.date, "%Y%m%d")
            return d.strftime("%d/%m/%Y")
        except Exception:
            return self.date


class KernelScanner:
    """Scan des kernels installés dans boot_pool.
    Indépendant de naming.sh — parse directement les noms de fichiers.
    """

    def __init__(self, boot: Path | None = None) -> None:
        self._boot = boot or BootPoolLocator.find() or _ZBM_LIVE_ROOT

    @property
    def boot(self) -> Path:
        return self._boot

    def kernels_dir(self) -> Path:
        return self._boot / "images" / "kernels"

    def initramfs_dir(self) -> Path:
        return self._boot / "images" / "initramfs"

    def modules_dir(self) -> Path:
        return self._boot / "images" / "modules"

    def _active_kernel_path(self) -> Path | None:
        """Chemin du kernel actif via $BOOT/boot/vmlinuz (symlink ZBM)."""
        link = self._boot / "boot" / "vmlinuz"
        if link.is_symlink():
            try:
                return link.resolve()
            except Exception:
                pass
        return None

    def _read_meta(self, img: Path) -> dict:
        meta = Path(str(img) + ".meta")
        if not meta.exists():
            return {}
        try:
            return json.loads(meta.read_text())
        except Exception:
            return {}

    def scan(self, include_failsafe: bool = False) -> list[KernelEntry]:
        """Scan et retourne tous les kernels installés, triés par date décroissante."""
        kdir = self.kernels_dir()
        mdir = self.modules_dir()
        if not kdir.exists():
            return []

        active_path = self._active_kernel_path()
        entries: list[KernelEntry] = []

        for f in sorted(kdir.iterdir()):
            if not f.is_file() or f.suffix == ".meta":
                continue
            img = NamingHelper.parse(f)
            if img is None:
                continue
            if img.type_ != "kernel":
                continue
            if not include_failsafe and img.system == "failsafe":
                continue

            meta = self._read_meta(f)
            kver = meta.get("kernel_ver", "") or ""
            size = f.stat().st_size if f.exists() else 0

            # Chercher le modules.sfs associé
            mpath = mdir / f"modules-{img.label}-{img.date}.sfs"
            has_mod = mpath.exists()
            mod_size = mpath.stat().st_size if has_mod else 0

            entries.append(KernelEntry(
                path=f,
                label=img.label,
                date=img.date,
                kver=kver,
                size_bytes=size,
                has_modules=has_mod,
                modules_path=mpath if has_mod else None,
                modules_size=mod_size,
                is_active=(active_path is not None and f.resolve() == active_path),
                meta=meta,
            ))

        return sorted(entries, key=lambda e: e.date, reverse=True)

    def scan_initramfs(self) -> list[ImageInfo]:
        """Liste les initramfs installés."""
        idir = self.initramfs_dir()
        if not idir.exists():
            return []
        result = []
        for f in sorted(idir.iterdir()):
            if not f.is_file() or f.suffix == ".meta":
                continue
            img = NamingHelper.parse(f)
            if img and img.type_ == "initramfs" and img.system != "failsafe":
                result.append(img)
        return sorted(result, key=lambda i: i.date, reverse=True)

    def latest_kernel(self) -> KernelEntry | None:
        kernels = self.scan()
        return kernels[0] if kernels else None

    def find_by_label(self, label: str) -> list[KernelEntry]:
        return [k for k in self.scan() if k.label == label]

    def initramfs_for_kernel(self, kernel: KernelEntry) -> list[ImageInfo]:
        """Initramfs compatibles avec ce kernel (même date ou indépendants)."""
        all_init = self.scan_initramfs()
        same_date = [i for i in all_init if i.date == kernel.date]
        return same_date if same_date else all_init


# ---------------------------------------------------------------------------
# DatasetManager — Miroir Python de lib/datasets-check.sh
# ---------------------------------------------------------------------------
@dataclass
class DatasetStatus:
    name:        str
    pool:        str
    mountpoint:  str
    exists:      bool
    canmount:    str   # "noauto" | "auto" | "on" | "off" | "?"
    used:        str
    actual_mp:   str
    description: str

    @property
    def ok(self) -> bool:
        return self.exists and (self.pool not in ("fast_pool",) or self.canmount == "noauto")

    @property
    def canmount_ok(self) -> bool:
        if self.pool == "fast_pool":
            return self.canmount == "noauto"
        return True


class DatasetManager:
    """Gestion des datasets ZFS.
    Miroir Python de lib/datasets-check.sh — indépendant des scripts bash.
    """

    BASE_DATASETS = [
        ("data_pool/home", "/home", "data_pool", "Répertoires utilisateurs partagés"),
    ]

    FAILSAFE_DATASETS = [
        # 1 seul dataset par système (overlay = upper OverlayFS)
        # /var /tmp vivent dans le lower (rootfs.sfs) et sont écrits dans l'upper
        ("fast_pool/overlay-failsafe", "none", "fast_pool", "Upper OverlayFS failsafe"),
    ]

    @staticmethod
    def datasets_for_system(system: str) -> list[tuple[str, str, str, str]]:
        """Retourne [(ds, mountpoint, pool, description)] pour un système."""
        # Architecture overlay : 1 seul dataset par système.
        # /var et /tmp sont dans le lower (rootfs.sfs) et redirigés vers l'upper.
        return [
            (f"fast_pool/overlay-{system}", "none", "fast_pool",
             f"Upper OverlayFS {system} (canmount=noauto, mountpoint=none)"),
        ]

    @staticmethod
    def _pool_imported(pool: str) -> bool:
        ok2, _ = run(["zpool", "list", pool])
        return ok2

    @staticmethod
    def _zfs_props(ds: str) -> dict[str, str]:
        ok2, out = run(["zfs", "get", "-H", "-o", "property,value",
                        "mountpoint,canmount,used", ds])
        if not ok2:
            return {}
        result = {}
        for line in out.splitlines():
            parts = line.split("\t")
            if len(parts) == 2:
                result[parts[0].strip()] = parts[1].strip()
        return result

    @classmethod
    def status(cls, system: str, include_failsafe: bool = False) -> list[DatasetStatus]:
        """Retourne l'état complet des datasets pour un système."""
        entries = list(cls.BASE_DATASETS) + cls.datasets_for_system(system)
        if include_failsafe:
            entries += cls.FAILSAFE_DATASETS

        result: list[DatasetStatus] = []
        for ds, mp, pool, desc in entries:
            pool_ok = cls._pool_imported(pool)
            if not pool_ok:
                result.append(DatasetStatus(
                    name=ds, pool=pool, mountpoint=mp, exists=False,
                    canmount="?", used="?", actual_mp="?",
                    description=f"{desc} [{pool} non importé]"
                ))
                continue
            props = cls._zfs_props(ds)
            exists = bool(props)
            result.append(DatasetStatus(
                name=ds, pool=pool, mountpoint=mp,
                exists=exists,
                canmount=props.get("canmount", "?"),
                used=props.get("used", "?"),
                actual_mp=props.get("mountpoint", "?"),
                description=desc,
            ))
        return result

    @classmethod
    def all_systems_status(cls, systems: list[str]) -> list[DatasetStatus]:
        """État complet pour tous les systèmes + failsafe."""
        result = []
        for s in systems:
            result.extend(cls.status(s, include_failsafe=False))
        result.extend(cls.FAILSAFE_DATASETS_STATUS())
        return result

    @classmethod
    def FAILSAFE_DATASETS_STATUS(cls) -> list[DatasetStatus]:
        result = []
        for ds, mp, pool, desc in cls.FAILSAFE_DATASETS:
            pool_ok = cls._pool_imported(pool)
            if not pool_ok:
                result.append(DatasetStatus(
                    name=ds, pool=pool, mountpoint=mp, exists=False,
                    canmount="?", used="?", actual_mp="?", description=desc
                ))
                continue
            props = cls._zfs_props(ds)
            result.append(DatasetStatus(
                name=ds, pool=pool, mountpoint=mp,
                exists=bool(props),
                canmount=props.get("canmount", "?"),
                used=props.get("used", "?"),
                actual_mp=props.get("mountpoint", "?"),
                description=desc,
            ))
        return result

    @classmethod
    def create(cls, ds: str, mountpoint: str, generator: "Generator[str, None, tuple[bool, str]]" = None) -> Generator[str, None, tuple[bool, str]]:  # type: ignore
        """Crée un dataset ZFS. Yield log lines, return (ok, msg)."""
        pool = ds.split("/")[0]
        yield f"  zfs create → {ds}"
        if not cls._pool_imported(pool):
            yield f"  ❌ {pool} non importé"
            return False, f"{pool} non importé"

        # Créer le parent si nécessaire
        parent = "/".join(ds.split("/")[:-1])
        if parent != pool:
            ok2, _ = run(["zfs", "list", parent])
            if not ok2:
                yield f"  Création parent : {parent}"
                run(["zfs", "create", "-o", "canmount=noauto",
                     "-o", "mountpoint=none", "-o", "compression=zstd", parent])

        cmd = ["zfs", "create",
               "-o", f"compression=zstd",
               "-o", "atime=off",
               "-o", f"mountpoint={mountpoint}"]
        if ds.startswith("fast_pool/"):
            cmd += ["-o", "canmount=noauto"]
        cmd.append(ds)

        ok2, msg = run(cmd)
        if ok2:
            yield f"  ✅ Créé : {ds}"
            return True, f"créé : {ds}"
        yield f"  ❌ Erreur : {msg}"
        return False, msg

    @classmethod
    def create_for_system(cls, system: str) -> Generator[str, None, tuple[bool, str]]:
        """Crée tous les datasets manquants pour un système."""
        yield f"Création datasets pour : {system}"
        ok_all = True
        for ds, mp, pool, desc in cls.datasets_for_system(system):
            ok2, _ = run(["zfs", "list", ds])
            if ok2:
                yield f"  ✓ Existe : {ds}"
                continue
            gen = cls.create(ds, mp)
            try:
                while True:
                    yield next(gen)
            except StopIteration as e:
                if not e.value[0]:
                    ok_all = False
        msg = f"Datasets {'créés' if ok_all else 'partiellement créés'} pour {system}"
        return ok_all, msg

    @staticmethod
    def detect_systems_from_zfs() -> list[str]:
        """Détecte les systèmes depuis les datasets fast_pool/overlay-*."""
        ok2, out = run(["zfs", "list", "-H", "-o", "name"])
        if not ok2:
            return []
        systems = []
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("fast_pool/overlay-") and "failsafe" not in line:
                sysname = line[len("fast_pool/overlay-"):]
                if sysname:
                    systems.append(sysname)
        return sorted(systems)


# ---------------------------------------------------------------------------
# PoolManager — Miroir Python de la section pools de detect.sh
# ---------------------------------------------------------------------------
@dataclass
class PoolInfo:
    name:    str
    state:   str    # "imported" | "importable" | "missing"
    health:  str    # ONLINE | DEGRADED | FAULTED | ""
    size:    str
    used:    str
    free:    str
    vdevs:   list[str]


class PoolManager:
    """Gestion des pools ZFS."""

    @staticmethod
    def list_imported() -> list[str]:
        ok2, out = run(["zpool", "list", "-H", "-o", "name"])
        if not ok2:
            return []
        return [l.strip() for l in out.splitlines() if l.strip()]

    @staticmethod
    def list_importable() -> list[str]:
        ok2, out = run(["zpool", "import"])
        if not ok2:
            return []
        result = []
        for line in out.splitlines():
            if line.strip().startswith("pool:"):
                name = line.split(":")[-1].strip()
                result.append(name)
        return result

    @classmethod
    def info(cls, pool: str) -> PoolInfo:
        imported = cls.list_imported()
        if pool in imported:
            ok2, out = run(["zpool", "list", "-H", "-o", "name,health,size,used,free", pool])
            if ok2:
                parts = out.strip().split("\t")
                health = parts[1] if len(parts) > 1 else "?"
                size   = parts[2] if len(parts) > 2 else "?"
                used   = parts[3] if len(parts) > 3 else "?"
                free   = parts[4] if len(parts) > 4 else "?"
                # Vdevs
                ok2v, vout = run(["zpool", "status", "-P", pool])
                vdevs = []
                if ok2v:
                    for vline in vout.splitlines():
                        vl = vline.strip()
                        if vl.startswith("/dev/"):
                            vdevs.append(vl.split()[0])
                return PoolInfo(name=pool, state="imported", health=health,
                                size=size, used=used, free=free, vdevs=vdevs)
            return PoolInfo(name=pool, state="imported", health="?",
                            size="?", used="?", free="?", vdevs=[])
        if pool in cls.list_importable():
            return PoolInfo(name=pool, state="importable", health="",
                            size="?", used="?", free="?", vdevs=[])
        return PoolInfo(name=pool, state="missing", health="",
                        size="?", used="?", free="?", vdevs=[])

    @staticmethod
    def import_pool(pool: str, force: bool = False) -> tuple[bool, str]:
        cmd = ["zpool", "import"]
        if force:
            cmd.append("-f")
        cmd.append(pool)
        return run(cmd)

    @staticmethod
    def export_pool(pool: str) -> tuple[bool, str]:
        return run(["zpool", "export", pool])


# ---------------------------------------------------------------------------
# KernelInstallManager — Miroir Python de lib/kernel.sh
# Installation d'un kernel + modules dans boot_pool depuis le live.
# ---------------------------------------------------------------------------
class KernelInstallManager:
    """Installation d'un kernel et de ses modules dans boot_pool.
    Miroir Python complet de lib/kernel.sh.
    Indépendant du script bash — exécute les opérations directement.
    """

    def __init__(self, boot: Path | None = None) -> None:
        self._boot = boot or BootPoolLocator.find() or _ZBM_LIVE_ROOT
        self._scanner = KernelScanner(self._boot)

    @property
    def boot(self) -> Path:
        return self._boot

    def find_kernel_in_live(self, from_rootfs: Path | None = None) -> Path | None:
        """Cherche le kernel source dans le live ou un rootfs squashfs monté."""
        search_dirs: list[Path] = []
        if from_rootfs:
            search_dirs.append(from_rootfs / "boot")
        # Live Debian/Ubuntu
        for live in ["/run/live/medium/live", "/run/live/medium/boot",
                     "/live/image/live", "/cdrom/live", "/media/cdrom/live"]:
            p = Path(live)
            if p.is_dir():
                search_dirs.append(p)
        # /boot du live seulement si != boot_pool
        if (Path("/boot") != self._boot) and Path("/boot/images").exists():
            search_dirs.append(Path("/boot"))

        patterns = ["vmlinuz-*", "vmlinuz", "kernel-*", "bzImage"]
        for d in search_dirs:
            for pat in patterns:
                found = sorted(d.glob(pat))
                if found:
                    return found[-1]  # le plus récent si plusieurs
        return None

    def find_modules_in_live(self, kver: str, from_rootfs: Path | None = None) -> Path | None:
        """Cherche /lib/modules/<kver> dans le live ou rootfs."""
        mod_bases: list[Path] = []
        if from_rootfs:
            mod_bases.append(from_rootfs / "lib" / "modules")
        mod_bases.append(Path("/lib/modules"))

        for base in mod_bases:
            if not base.is_dir():
                continue
            # Correspondance exacte
            exact = base / kver
            if exact.is_dir():
                return exact
            # Correspondance partielle
            for d in sorted(base.iterdir()):
                if d.is_dir() and kver in d.name:
                    return d
            # Premier disponible
            first = sorted(base.iterdir())
            if first:
                return first[-1]
        return None

    def install(
        self, label: str, date: str | None = None,
        kernel_src: Path | None = None,
        modules_src: Path | None = None,
        from_rootfs: Path | None = None,
        no_modules: bool = False,
    ) -> Generator[str, None, tuple[bool, str]]:
        """Installe kernel + modules dans boot_pool.
        Yield log lines, return (ok, msg).
        """
        today = date or datetime.now().strftime("%Y%m%d")
        kdir = self._boot / "images" / "kernels"
        mdir = self._boot / "images" / "modules"
        kdir.mkdir(parents=True, exist_ok=True)
        mdir.mkdir(parents=True, exist_ok=True)

        stem_k = f"kernel-{label}-{today}"
        stem_m = f"modules-{label}-{today}.sfs"
        dst_k = kdir / stem_k
        dst_m = mdir / stem_m

        yield f"  Label    : {label}"
        yield f"  Kernel → : {dst_k}"
        if not no_modules:
            yield f"  Modules→ : {dst_m}"

        # Vérifier overwrite
        for dst in [dst_k, dst_m]:
            if dst.exists():
                yield f"  ⚠ {dst.name} existe déjà — sera écrasé"

        # Trouver le kernel source
        if kernel_src is None:
            kernel_src = self.find_kernel_in_live(from_rootfs)
        if kernel_src is None or not kernel_src.exists():
            yield "  ❌ Kernel source introuvable"
            return False, "kernel source introuvable"
        yield f"  Source   : {kernel_src}"

        # Déduire kver depuis le nom du fichier
        kname = kernel_src.name
        kver = re.sub(r'^vmlinuz-?', '', kname) or "unknown"
        if kver in ("vmlinuz", "bzImage", ""):
            kver = "unknown"
        yield f"  kver     : {kver}"

        # Copier le kernel
        import shutil
        try:
            shutil.copy2(str(kernel_src), str(dst_k))
            dst_k.chmod(0o444)
            yield f"  ✅ kernel copié  ({human_size(dst_k.stat().st_size)})"
        except Exception as exc:
            yield f"  ❌ Copie kernel : {exc}"
            return False, str(exc)

        # Modules squashfs
        if not no_modules:
            if modules_src is None:
                modules_src = self.find_modules_in_live(kver, from_rootfs)
                if modules_src:
                    # kver réelle depuis le répertoire de modules
                    kver = modules_src.name
                    yield f"  kver (modules) : {kver}"

            if modules_src and modules_src.is_dir():
                yield f"  Construction modules.sfs depuis {modules_src} ..."
                ok2, msg = run([
                    "mksquashfs", str(modules_src), str(dst_m),
                    "-comp", "zstd", "-Xcompression-level", "6", "-noappend", "-quiet"
                ], timeout=300)
                if ok2:
                    dst_m.chmod(0o444)
                    yield f"  ✅ modules.sfs  ({human_size(dst_m.stat().st_size)})"
                else:
                    yield f"  ❌ mksquashfs : {msg}"
                    no_modules = True
            else:
                yield "  ⚠ Modules introuvables — modules.sfs non généré"
                no_modules = True

        # Écrire les .meta
        meta_k = {
            "type": "kernel", "system": "", "label": label, "date": today,
            "built": datetime.now().isoformat(), "kernel_ver": kver,
            "init_type": "", "size_bytes": dst_k.stat().st_size,
            "sha256": "", "builder": "KernelInstallManager",
        }
        try:
            meta_k["sha256"] = hashlib.sha256(dst_k.read_bytes()).hexdigest()
        except Exception:
            pass
        Path(str(dst_k) + ".meta").write_text(json.dumps(meta_k, indent=2) + "\n")
        yield "  ✅ .meta kernel"

        if not no_modules and dst_m.exists():
            meta_m = dict(meta_k)
            meta_m.update({"type": "modules",
                           "size_bytes": dst_m.stat().st_size,
                           "sha256": hashlib.sha256(dst_m.read_bytes()).hexdigest()})
            Path(str(dst_m) + ".meta").write_text(json.dumps(meta_m, indent=2) + "\n")
            yield "  ✅ .meta modules"

        # Mettre à jour config.sh
        cfg = ConfigManager()
        if cfg.get_path():
            if cfg.set("KERNEL_LABEL", label):
                yield f"  ✅ KERNEL_LABEL={label} → config.sh"
            if kver != "unknown" and cfg.set("KERNEL_VER", kver):
                yield f"  ✅ KERNEL_VER={kver} → config.sh"

        yield ""
        yield f"  ✅ Kernel installé : kernel-{label}-{today}  kver={kver}"
        return True, f"kernel-{label}-{today} installé"

    def delete(self, entry: KernelEntry) -> tuple[bool, str]:
        """Supprime un kernel et son modules.sfs du boot_pool."""
        try:
            entry.path.unlink(missing_ok=True)
            Path(str(entry.path) + ".meta").unlink(missing_ok=True)
            if entry.modules_path:
                entry.modules_path.unlink(missing_ok=True)
                Path(str(entry.modules_path) + ".meta").unlink(missing_ok=True)
            return True, f"{entry.filename} supprimé"
        except Exception as exc:
            return False, str(exc)


# ---------------------------------------------------------------------------
# InitramfsBuilder — Miroir Python de lib/initramfs.sh
# ---------------------------------------------------------------------------
class InitramfsBuilder:
    """Construction d'un initramfs sans dracut.
    Miroir Python de lib/initramfs.sh — indépendant du script bash.
    """

    INIT_TYPES = {
        "zbm":        "Init complet : overlay + pivot_root + Python TUI",
        "zbm-stream": "Variante stream seule, sans TUI",
        "minimal":    "Init natif noyau (requiert dracut + kver cible)",
        "custom":     "Init personnalisé",
    }

    def __init__(self, boot: Path | None = None, deploy_dir: Path | None = None) -> None:
        self._boot = boot or BootPoolLocator.find() or _ZBM_LIVE_ROOT
        # Répertoire deploy contenant initramfs-init
        self._deploy = deploy_dir or self._find_deploy_dir()

    def _find_deploy_dir(self) -> Path | None:
        candidates = [
            Path("/etc/zfsbootmenu"),
            BOOT.parent / "deploy",
            BOOT / "deploy",
            Path("/root/deploy"),
        ]
        for c in candidates:
            if (c / "initramfs-init").exists():
                return c
        return None

    def init_file(self, init_type: str) -> Path | None:
        """Retourne le chemin du fichier init source pour ce type."""
        if self._deploy is None:
            return None
        if init_type == "zbm":
            p = self._deploy / "initramfs-init"
            return p if p.exists() else None
        if init_type == "zbm-stream":
            p = self._deploy / "initramfs-stream-init"
            return p if p.exists() else None
        if init_type.startswith("custom-"):
            p = self._deploy / f"{init_type}-init"
            return p if p.exists() else None
        return None

    def list_available(self) -> list[ImageInfo]:
        """Initramfs installés dans boot_pool."""
        idir = self._boot / "images" / "initramfs"
        if not idir.exists():
            return []
        result = []
        for f in sorted(idir.iterdir()):
            if not f.is_file() or f.suffix == ".meta":
                continue
            img = NamingHelper.parse(f)
            if img and img.type_ == "initramfs" and img.system != "failsafe":
                result.append(img)
        return sorted(result, key=lambda i: i.date, reverse=True)

    def build(
        self, init_type: str, date: str | None = None, kver_for_minimal: str = ""
    ) -> Generator[str, None, tuple[bool, str]]:
        """Construit un initramfs. Yield log lines, return (ok, msg)."""
        import shutil, subprocess, tempfile
        today = date or datetime.now().strftime("%Y%m%d")
        idir = self._boot / "images" / "initramfs"
        idir.mkdir(parents=True, exist_ok=True)
        stem = f"initramfs-{init_type}-{today}.img"
        dst = idir / stem
        yield f"  Type  : {init_type}"
        yield f"  Cible : {dst}"

        # Cas minimal — dracut
        if init_type == "minimal":
            yield from self._build_minimal(dst, kver_for_minimal, today)
            return

        # Cas zbm / zbm-stream / custom-*
        init_file = self.init_file(init_type)
        if init_file is None:
            yield f"  ❌ init source introuvable pour type '{init_type}'"
            yield f"     (cherché dans {self._deploy})"
            return False, "init source introuvable"

        yield f"  Init  : {init_file}"
        inject = Path(tempfile.mkdtemp(prefix="zbm-initramfs-"))
        try:
            yield from self._build_cpio(init_file, inject, dst, init_type, today)
        finally:
            shutil.rmtree(str(inject), ignore_errors=True)

    def _build_minimal(
        self, dst: Path, kver: str, today: str
    ) -> Generator[str, None, tuple[bool, str]]:
        import subprocess
        ok2, _ = run(["which", "dracut"])
        if not ok2:
            yield "  ❌ dracut non installé (requis pour type minimal)"
            return False, "dracut absent"
        if not kver:
            yield "  ❌ kver requise pour type minimal"
            return False, "kver manquante"
        if not Path(f"/lib/modules/{kver}").is_dir():
            yield f"  ❌ /lib/modules/{kver} absent — impossible depuis ce live"
            return False, "modules absents"

        import tempfile
        conf_f = Path(tempfile.mktemp(suffix=".conf"))
        conf_f.write_text(
            'add_dracutmodules+=" kernel-modules base "\n'
            'omit_dracutmodules+=" nfs iscsi multipath biosdevname systemd "\n'
            'add_drivers+=" zfs squashfs overlay e1000e i915 loop "\n'
            'compress="zstd"\n'
        )
        yield f"  dracut --kver {kver} ..."
        ok2, msg = run([
            "dracut", "--conf", str(conf_f), "--force", "--no-hostonly",
            "--kver", kver, str(dst)
        ], timeout=300)
        conf_f.unlink(missing_ok=True)
        if ok2:
            dst.chmod(0o444)
            yield f"  ✅ {dst.name}  ({human_size(dst.stat().st_size)})"
            self._write_meta(dst, "minimal", kver, today)
            yield "  ✅ .meta"
            return True, f"{dst.name} construit"
        yield f"  ❌ dracut : {msg}"
        return False, msg

    def _build_cpio(
        self, init_file: Path, inject: Path, dst: Path, init_type: str, today: str
    ) -> Generator[str, None, tuple[bool, str]]:
        import shutil, stat

        # Structure de base
        for d in ["bin", "sbin", "usr/bin", "usr/sbin", "lib", "lib64",
                  "lib/x86_64-linux-gnu", "proc", "sys", "dev", "run", "tmp",
                  "mnt/boot", "mnt/boot/images", "mnt/lower", "mnt/fast", "mnt/merged",
                  "mnt/modloop", "mnt/python", "mnt/work", "mnt/tmp"]:
            (inject / d).mkdir(parents=True, exist_ok=True)

        # /init
        shutil.copy2(str(init_file), str(inject / "init"))
        (inject / "init").chmod(0o755)
        yield "  /init installé"

        # Copier un binaire + ses libs
        def copy_bin(src: str, dst_dir: Path = inject / "bin") -> bool:
            p = Path(src)
            if not p.exists():
                return False
            dst_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, str(dst_dir / p.name))
            ok2, out = run(["ldd", src])
            if ok2:
                for ln in out.splitlines():
                    m = re.search(r'=> (/\S+)', ln) or re.match(r'\s+(/\S+)', ln)
                    if m:
                        lib = Path(m.group(1))
                        if lib.exists():
                            d2 = inject / lib.parent.relative_to("/")
                            d2.mkdir(parents=True, exist_ok=True)
                            try:
                                shutil.copy2(str(lib), str(d2 / lib.name))
                                if lib.is_symlink():
                                    real = lib.resolve()
                                    if real.exists():
                                        shutil.copy2(str(real), str(d2 / real.name))
                            except Exception:
                                pass
            return True

        # busybox en priorité
        bb = shutil.which("busybox")
        if bb:
            copy_bin(bb)
            for applet in ["sh", "ash", "mount", "umount", "mkdir", "sleep",
                           "cat", "echo", "ln", "cp", "modprobe", "insmod", "depmod"]:
                link = inject / "bin" / applet
                if not link.exists():
                    link.symlink_to("busybox")
            yield "  busybox + applets"
        else:
            yield "  ⚠ busybox absent — binaires individuels"
            for b in ["sh", "bash", "mount", "umount", "mkdir", "sleep", "cat", "ln", "cp"]:
                found = shutil.which(b)
                if found:
                    copy_bin(found)
            for b in ["modprobe", "insmod", "depmod"]:
                found = shutil.which(b)
                if found:
                    copy_bin(found, inject / "sbin")

        # zfs/zpool
        for b in ["zfs", "zpool"]:
            found = shutil.which(b)
            if found:
                copy_bin(found, inject / "sbin")
            else:
                yield f"  ⚠ {b} absent du live"

        # mountpoint, pivot_root, switch_root
        for b in ["mountpoint", "pivot_root", "switch_root"]:
            found = shutil.which(b)
            if found:
                dst_dir2 = inject / "bin" if b == "mountpoint" else inject / "sbin"
                copy_bin(found, dst_dir2)

        # ld-linux
        for ld in ["/lib64/ld-linux-x86-64.so.2", "/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2"]:
            if Path(ld).exists():
                d2 = inject / Path(ld).parent.relative_to("/")
                d2.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ld, str(d2 / Path(ld).name))
                break

        # Symlinks de compat
        for lnk, tgt in [("sbin/init", "/init"), ("usr/bin/sh", "/bin/sh")]:
            lp = inject / lnk
            if not lp.exists():
                try:
                    lp.symlink_to(tgt)
                except Exception:
                    pass

        sz = human_size(sum(f.stat().st_size for f in inject.rglob("*") if f.is_file()))
        yield f"  Staging : {sz}"

        # cpio + zstd
        # Pipeline : find . -print0 | cpio --null -o -H newc | zstd -5 > dst
        # Le sort (bash) n'est pas reproduit ici — pas critique pour le fonctionnement
        yield "  Packaging cpio + zstd ..."
        import subprocess
        _dst_fd = open(str(dst), "wb")
        try:
            cpio_proc = subprocess.Popen(
                ["find", ".", "-print0"],
                cwd=str(inject), stdout=subprocess.PIPE
            )
            cpio_pack = subprocess.Popen(
                ["cpio", "--null", "-o", "-H", "newc", "--quiet"],
                cwd=str(inject),
                stdin=cpio_proc.stdout, stdout=subprocess.PIPE
            )
            if cpio_proc.stdout:
                cpio_proc.stdout.close()
            zstd_proc = subprocess.Popen(
                ["zstd", "-5", "-q"],
                stdin=cpio_pack.stdout, stdout=_dst_fd
            )
            if cpio_pack.stdout:
                cpio_pack.stdout.close()
            zstd_proc.wait()
            cpio_pack.wait()
            cpio_proc.wait()
        finally:
            _dst_fd.close()

        if dst.exists() and dst.stat().st_size > 0:
            dst.chmod(0o444)
            yield f"  ✅ {dst.name}  ({human_size(dst.stat().st_size)})"
        else:
            yield "  ❌ initramfs vide ou erreur cpio"
            return False, "initramfs vide"

        # kver depuis kernel installé
        scanner = KernelScanner(self._boot)
        latest = scanner.latest_kernel()
        kver_meta = latest.kver if latest else "independent"
        self._write_meta(dst, init_type, kver_meta, today)
        yield "  ✅ .meta"
        return True, f"{dst.name} construit"

    def _write_meta(self, dst: Path, init_type: str, kver: str, today: str) -> None:
        meta = {
            "type": "initramfs", "system": "", "label": init_type, "date": today,
            "built": datetime.now().isoformat(), "kernel_ver": kver,
            "init_type": init_type,
            "size_bytes": dst.stat().st_size if dst.exists() else 0,
            "sha256": hashlib.sha256(dst.read_bytes()).hexdigest() if dst.exists() else "",
            "builder": "InitramfsBuilder",
        }
        Path(str(dst) + ".meta").write_text(json.dumps(meta, indent=2) + "\n")


# ---------------------------------------------------------------------------
# RootfsInstallManager — Miroir Python de lib/rootfs.sh
# ---------------------------------------------------------------------------
class RootfsInstallManager:
    """Installation d'un rootfs squashfs dans boot_pool.
    Miroir Python de lib/rootfs.sh.
    """

    def __init__(self, boot: Path | None = None) -> None:
        self._boot = boot or BootPoolLocator.find() or _ZBM_LIVE_ROOT

    def find_rootfs_on_live(self) -> list[Path]:
        """Cherche des rootfs.sfs sur le support live et dans boot_pool."""
        found: list[Path] = []
        # Dans boot_pool
        rdir = self._boot / "images" / "rootfs"
        if rdir.exists():
            found.extend(sorted(rdir.glob("rootfs-*.sfs")))
        # Sur le live
        for base in ["/run/live/medium", "/live/image", "/cdrom", "/media", "/mnt"]:
            p = Path(base)
            if p.is_dir():
                found.extend(sorted(p.rglob("rootfs*.sfs")))
        return found

    def install(
        self, src: Path, system: str, label: str, date: str | None = None
    ) -> Generator[str, None, tuple[bool, str]]:
        """Installe un rootfs.sfs dans boot_pool."""
        import shutil
        today = date or datetime.now().strftime("%Y%m%d")
        rdir = self._boot / "images" / "rootfs"
        rdir.mkdir(parents=True, exist_ok=True)
        stem = f"rootfs-{system}-{label}-{today}.sfs"
        dst = rdir / stem

        yield f"  Source  : {src}"
        yield f"  Cible   : {dst}"

        if not src.exists():
            yield f"  ❌ Source introuvable : {src}"
            return False, "source introuvable"

        # Vérifier que c'est un squashfs
        ok2, fout = run(["file", str(src)])
        if ok2 and "squashfs" not in fout.lower():
            yield f"  ⚠ {src.name} ne semble pas être un squashfs"

        yield f"  Copie ({human_size(src.stat().st_size)}) ..."
        try:
            shutil.copy2(str(src), str(dst))
            dst.chmod(0o444)
            yield f"  ✅ {dst.name}  ({human_size(dst.stat().st_size)})"
        except Exception as exc:
            yield f"  ❌ Copie : {exc}"
            return False, str(exc)

        meta = {
            "type": "rootfs", "system": system, "label": label, "date": today,
            "built": datetime.now().isoformat(), "kernel_ver": "", "init_type": "",
            "size_bytes": dst.stat().st_size,
            "sha256": hashlib.sha256(dst.read_bytes()).hexdigest(),
            "builder": "RootfsInstallManager",
        }
        Path(str(dst) + ".meta").write_text(json.dumps(meta, indent=2) + "\n")
        yield "  ✅ .meta"
        return True, f"{stem} installé"


# ---------------------------------------------------------------------------
# DeployOrchestrator — Miroir Python de deploy.sh
# Exécute les étapes de déploiement dans l'ordre.
# ---------------------------------------------------------------------------
class DeployOrchestrator:
    """Orchestrateur de déploiement — miroir Python de deploy.sh.
    Chaque étape est une méthode qui yield des lignes de log.
    """

    def __init__(self) -> None:
        self._cfg  = ConfigManager()
        self._boot_locator = BootPoolLocator()
        self._boot: Path | None = None
        self._scanner: KernelScanner | None = None

    def boot(self) -> Path:
        if self._boot is None:
            self._boot = BootPoolLocator.find() or BOOT
        return self._boot

    def scanner(self) -> KernelScanner:
        if self._scanner is None:
            self._scanner = KernelScanner(self.boot())
        return self._scanner

    # Étape 1 : Détection
    def step_detect(self) -> Generator[str, None, tuple[bool, str]]:
        yield "=== Étape 1 : Détection de l'environnement ==="
        # NVMe
        ok2, nvme_out = run(["ls", "/dev/nvme*n1"])
        if ok2:
            for line in nvme_out.splitlines():
                yield f"  NVMe : {line.strip()}"
        else:
            yield "  ⚠ Aucun NVMe détecté"
        # Pools
        pm = PoolManager()
        for pool in ["boot_pool", "fast_pool", "data_pool"]:
            info = pm.info(pool)
            icon = "✅" if info.state == "imported" else ("⚠" if info.state == "importable" else "❌")
            yield f"  {icon} {pool} : {info.state}  {info.health}  {info.size}"
        # boot_pool localisé
        b = BootPoolLocator.find()
        if b:
            yield f"  ✅ boot_pool → {b}"
            self._boot = b
            self._scanner = KernelScanner(b)
        else:
            yield "  ⚠ boot_pool non localisé (normal si non encore créé)"
        return True, "détection OK"

    # Étape 2 : Datasets
    def step_datasets(self, systems: list[str]) -> Generator[str, None, tuple[bool, str]]:
        yield "=== Étape 2 : Vérification des datasets ZFS ==="
        dm = DatasetManager()
        all_ok = True
        for sys in systems:
            for s in dm.status(sys):
                icon = "✅" if s.ok else ("⚠" if s.exists else "❌")
                canm = f"  canmount={s.canmount}" if not s.canmount_ok else ""
                yield f"  {icon} {s.name:<40}  {s.used:<8}{canm}"
                if not s.ok:
                    all_ok = False
        return all_ok, "datasets OK" if all_ok else "datasets manquants"

    # Étape 3 : Kernel
    def step_kernel_info(self) -> Generator[str, None, tuple[bool, str]]:
        yield "=== Étape 3 : Kernels dans boot_pool ==="
        kernels = self.scanner().scan()
        if not kernels:
            yield "  ❌ Aucun kernel installé"
            return False, "aucun kernel"
        for k in kernels:
            active = " [actif]" if k.is_active else ""
            modules = f" + modules ({k.modules_size_human})" if k.has_modules else ""
            yield f"  ✅ kernel-{k.label}-{k.date}  kver={k.kver}  {k.size_human}{modules}{active}"
        return True, f"{len(kernels)} kernel(s)"

    # Étape 4 : Initramfs
    def step_initramfs_info(self) -> Generator[str, None, tuple[bool, str]]:
        yield "=== Étape 4 : Initramfs dans boot_pool ==="
        ib = InitramfsBuilder(self.boot())
        imgs = ib.list_available()
        if not imgs:
            yield "  ❌ Aucun initramfs installé"
            return False, "aucun initramfs"
        for img in imgs:
            meta = NamingHelper.read_meta(img.path)
            it = meta.get("init_type", img.label)
            yield f"  ✅ {img.filename:<48}  type={it}"
        return True, f"{len(imgs)} initramfs"

    # Étape 5 : Rootfs
    def step_rootfs_info(self) -> Generator[str, None, tuple[bool, str]]:
        yield "=== Étape 5 : Rootfs dans boot_pool ==="
        rim = RootfsInstallManager(self.boot())
        rootfs = NamingHelper.list_images("rootfs")
        if not rootfs:
            yield "  ⚠ Aucun rootfs (normal au premier déploiement)"
            return True, "aucun rootfs"
        for img in rootfs:
            yield f"  ✅ {img.filename:<52}  système={img.system}"
        return True, f"{len(rootfs)} rootfs"

    # Étape 7 : Presets
    def step_presets_info(self) -> Generator[str, None, tuple[bool, str]]:
        yield "=== Étape 7 : Presets de boot ==="
        if not PRESETS_DIR.exists():
            yield "  ❌ Répertoire presets absent"
            return False, "pas de presets"
        presets = list(PRESETS_DIR.glob("*.json"))
        if not presets:
            yield "  ⚠ Aucun preset généré"
            return False, "aucun preset"
        for pf in sorted(presets):
            try:
                d = json.loads(pf.read_text())
                yield f"  ✅ {d.get('name','?'):<20}  {d.get('type','?'):<12}  {d.get('_kernel_ver','?')}"
            except Exception:
                yield f"  ❌ {pf.name} illisible"
        return True, f"{len(presets)} presets"

    # Résumé global
    def full_status(self, systems: list[str]) -> Generator[str, None, None]:
        for gen in [
            self.step_detect(),
            self.step_datasets(systems),
            self.step_kernel_info(),
            self.step_initramfs_info(),
            self.step_rootfs_info(),
            self.step_presets_info(),
        ]:
            try:
                while True:
                    line = next(gen)
                    yield line
            except StopIteration:
                pass
            yield ""


# =============================================================================
# PRESET MANAGER
# =============================================================================
class PresetManager:
    def load(self) -> list[dict]:
        presets: list[dict] = []
        if not PRESETS_DIR.exists(): return presets
        for f in sorted(PRESETS_DIR.glob("*.json")):
            try:
                d = json.loads(f.read_text())
                d["_file"] = str(f)
                presets.append(d)
            except: continue
        return sorted(presets, key=lambda p: p.get("priority", 50))

    def save(self, preset: dict) -> bool:
        path = Path(preset.get("_file", ""))
        if not path.exists():
            name = preset.get("name","unknown")
            path = PRESETS_DIR / f"{name}.json"
        clean = {k:v for k,v in preset.items() if not k.startswith("_")}
        tmp = path.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps(clean, indent=4))
            tmp.rename(path)
            return True
        except: return False

    def active_name(self) -> str | None:
        """Retourne le nom du preset actif, détecté via $BOOT/boot/vmlinuz."""
        link = BOOT / "boot" / "vmlinuz"
        if not link.is_symlink(): return None
        try:
            target = str(link.resolve())
        except Exception:
            return None
        for p in self.load():
            if p.get("protected"): continue
            k = p.get("kernel", "")
            if not k: continue
            try:
                if str(Path(k).resolve()) == target:
                    return p.get("name")
            except Exception:
                pass
        return None

    def set_active(self, preset: dict) -> tuple[bool, str]:
        """Met à jour les symlinks actifs depuis un preset.
        
        ⚠️  ATTENTION : modifie les symlinks $BOOT/vmlinuz, initrd.img, etc.
        ($BOOT = /mnt/zbm/boot sur live, /boot sur système installé)
        Ces changements prennent effet au prochain redémarrage.
        
        kernel/initramfs/modules : indépendants du rootfs
        rootfs=null : valide pour les presets initiaux ou minimaux
        """
        if preset.get("protected"):
            return False, "Preset protégé — modification interdite"

        errors: list[str] = []
        # Répertoire des symlinks = $BOOT/boot/ (ZBM cherche <BE>/boot/vmlinuz)
        links_dir = BOOT / "boot"
        links_dir.mkdir(parents=True, exist_ok=True)

        def _make_link(link_name: str, target_path: str, required: bool = True) -> None:
            """Crée un symlink RELATIF dans $BOOT/boot/ → target (dans $BOOT/images/…)."""
            link = links_dir / link_name
            if not target_path or target_path == "null":
                link.unlink(missing_ok=True)
                return
            tgt = Path(target_path)
            if not tgt.exists():
                msg = f"❌ {link_name}: fichier introuvable → {target_path}"
                if required:
                    errors.append(msg)
                else:
                    errors.append(msg.replace("❌", "⚠"))
                return
            try:
                # Symlink RELATIF : portabilité si boot_pool remonté ailleurs
                rel = Path(os.path.relpath(tgt, links_dir))
                link.unlink(missing_ok=True)
                link.symlink_to(rel)
            except Exception as exc:
                errors.append(f"{'❌' if required else '⚠'} {link_name}: {exc}")

        # Kernel + initramfs : requis
        _make_link("vmlinuz",   preset.get("kernel", ""),    required=True)
        _make_link("initrd.img",preset.get("initramfs", ""), required=True)
        # Modules + rootfs : optionnels
        _make_link("modules.sfs", preset.get("modules") or "", required=False)
        _make_link("rootfs.sfs",  preset.get("rootfs")  or "", required=False)

        # Mettre à jour _image_set depuis le kernel .meta
        k_path = preset.get("kernel", "")
        if k_path and Path(k_path).exists():
            meta = NamingHelper.read_meta(Path(k_path))
            preset["_kernel_ver"] = meta.get("kernel_ver", "")
            img = NamingHelper.parse(Path(k_path))
            if img:
                preset["_image_set"] = f"{img.label}/{img.date}"
            self.save(preset)

        return (not errors), ("\n".join(errors) if errors else f"✅ Actif: {preset.get('name')}")

    def build_preset(self,
                     name: str,
                     label: str,
                     preset_type: str,
                     init_type: str,
                     kernel_path: str,
                     initramfs_path: str,
                     modules_path: str | None = None,
                     rootfs_path: str | None = None,
                     rootfs_system: str = "",
                     priority: int = 10,
                     stream_key: str = "",
                     exec_cmd: str = "",
                     extra: dict | None = None) -> dict:
        """Construit un preset complet depuis les composants fournis.
        
        ⚠️  Les fichiers doivent exister avant d'appeler cette méthode.
        kernel/initramfs/modules sont INDÉPENDANTS du rootfs.
        rootfs=None : valide pour les presets initiaux/minimaux.
        """
        k_meta = NamingHelper.read_meta(Path(kernel_path)) if kernel_path else {}
        i_meta = NamingHelper.read_meta(Path(initramfs_path)) if initramfs_path else {}
        k_img  = NamingHelper.parse(Path(kernel_path))  if kernel_path else None
        i_img  = NamingHelper.parse(Path(initramfs_path)) if initramfs_path else None
        r_img  = NamingHelper.parse(Path(rootfs_path)) if rootfs_path else None

        image_set = ""
        if k_img: image_set = f"{k_img.label}/{k_img.date}"
        if r_img: image_set += f" + {r_img.system}/{r_img.label}/{r_img.date}"

        # Cmdline de base
        cmdline = "quiet loglevel=3"
        if rootfs_system: cmdline += f" zbm_system={rootfs_system}"
        elif name: cmdline += f" zbm_system={name}"
        if rootfs_path and rootfs_path != "null":
            cmdline += f" zbm_rootfs={rootfs_path}"
        else:
            cmdline += " zbm_rootfs=none"
            if exec_cmd and exec_cmd not in ("", "none"):
                cmdline += f" zbm_exec={exec_cmd}"
        if modules_path: cmdline += f" zbm_modules={modules_path}"
        if rootfs_system:
            # zbm_var supprimé — architecture overlay
            # zbm_log supprimé — architecture overlay
            cmdline += f" zbm_overlay=fast_pool/overlay-{rootfs_system}"

        preset = {
            "_generated":   datetime.now().isoformat(),
            "_image_set":   image_set,
            "_kernel_ver":  k_meta.get("kernel_ver", ""),
            "name":         name,
            "label":        label,
            "priority":     priority,
            "protected":    False,
            "type":         preset_type,
            "init_type":    init_type or i_meta.get("init_type", "zbm"),
            "kernel":       kernel_path or "",
            "initramfs":    initramfs_path or "",
            "modules":      modules_path or None,
            "rootfs":       rootfs_path or None,
            "exec":         exec_cmd or "",
            "python_sfs":   None,
            "rootfs_label": r_img.label if r_img else "",
            # var_dataset / log_dataset / tmp_dataset : supprimés (architecture overlay)
            # /var /tmp gérés par l'upper overlay (fast_pool/overlay-<s>)
            "overlay_dataset": f"fast_pool/overlay-{rootfs_system}" if rootfs_system else None,
            "home_dataset":    "data_pool/home" if rootfs_system else None,
            "stream_key":      stream_key,
            "stream_resolution": "1920x1080",
            "stream_fps":       30,
            "stream_bitrate":   "4500k",
            "stream_delay_sec": 30,
            "network_mode":  "dhcp",
            "network_iface": "auto",
            "cmdline": cmdline,
        }
        if extra:
            preset.update(extra)
        return preset

    def symlink_status(self) -> list[dict]:
        r = []
        for name in ("vmlinuz", "initrd.img", "modules.sfs", "rootfs.sfs"):
            lp = BOOT / "boot" / name
            target = readlink(lp)
            img = NamingHelper.parse(Path(target)) if target != "—" else None
            r.append({
                "name": name, "target": target,
                "ok": lp.is_file(), "failsafe": False,
                "set_key": img.set_key if img else "—",
            })
        for name in FAILSAFE_SYMLINKS:
            lp = BOOT / "boot" / name
            target = readlink(lp)
            img = NamingHelper.parse(Path(target)) if target != "—" else None
            r.append({
                "name": name, "target": target,
                "ok": lp.is_file(), "failsafe": True,
                "set_key": img.set_key if img else "—",
            })
        return r


# =============================================================================
# STREAM MANAGER (interface avec zbm-startup via /run/)
# =============================================================================

class StreamManager:
    """Contrôle du stream YouTube via les fichiers d'état /run/zbm-*."""

    def state(self) -> str:
        return stream_state()

    def countdown(self) -> int:
        return stream_countdown()

    def cancel(self) -> bool:
        try:
            STREAM_STATE.write_text("cancelled")
            return True
        except: return False

    def stop(self) -> tuple[bool, str]:
        if STREAM_PID.exists():
            try:
                pid = int(STREAM_PID.read_text().strip())
                ok, msg = run(["kill", "-TERM", str(pid)])
                STREAM_STATE.write_text("stopped")
                return True, f"Stream arrêté (PID {pid})"
            except Exception as e:
                return False, str(e)
        return False, "PID stream introuvable"

    def start(self, preset: dict) -> tuple[bool, str]:
        """Lance ffmpeg directement (bypass zbm-startup, pour démarrage manuel)."""
        key   = preset.get("stream_key","")
        if not key: return False, "Clé stream non configurée"
        res   = preset.get("stream_resolution","1920x1080")
        fps   = int(preset.get("stream_fps", 30))
        rate  = preset.get("stream_bitrate","4500k")
        w,h   = res.split("x")
        url   = f"rtmp://a.rtmp.youtube.com/live2/{key}"

        cmd = [
            "ffmpeg","-y",
            "-f","fbdev","-framerate",str(fps),"-video_size",f"{w}x{h}","-i","/dev/fb0",
            "-f","alsa","-i","hw:0,0",
            "-c:v","libx264","-preset","veryfast","-tune","zerolatency",
            "-b:v",rate,"-maxrate",rate,"-bufsize",rate,
            "-pix_fmt","yuv420p","-g",str(fps*2),"-keyint_min",str(fps),
            "-c:a","aac","-b:a","128k","-ar","44100",
            "-f","flv", url,
        ]
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            STREAM_PID.write_text(str(proc.pid))
            STREAM_STATE.write_text("running")
            return True, f"Stream démarré (PID {proc.pid})"
        except Exception as e:
            return False, str(e)

    def tail_log(self, lines: int = 50) -> str:
        try:
            ok, out = run(["tail","-n",str(lines),str(ZBM_LOG)])
            return out
        except: return ""


# =============================================================================
# SNAPSHOT MANAGER
# =============================================================================

@dataclass
class SnapshotProfile:
    id:            str       = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name:          str       = ""
    system:        str       = "systeme1"
    rootfs_label:  str       = ""
    components:    list[str] = field(default_factory=lambda: ["var","log"])
    schedule:      str       = "none"
    schedule_hour: int       = 2
    retention:     int       = 7
    last_run:      str       = ""

    def snap_name(self, ts: str | None = None) -> str:
        ts = ts or datetime.now().strftime("%Y%m%d-%H%M%S")
        label = re.sub(r'[^\w.\-]', '-', self.rootfs_label or self.system)
        return f"{self.system}_{label}_{'+'.join(self.components)}_{ts}"

    def dataset_for(self, comp: str) -> str | None:
        # Architecture overlay : seul "ovl" (overlay-<s>) est un dataset ZFS.
        # "var"/"log"/"tmp" ne correspondent plus à des datasets — supprimés.
        tpls = {
            "ovl": f"fast_pool/overlay-{self.system}",  # upper OverlayFS (seul dataset)
                    }
        return tpls.get(comp)

    def to_dict(self) -> dict: return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> SnapshotProfile:
        return cls(**{k:v for k,v in d.items() if k in cls.__dataclass_fields__})  # type: ignore


class ProfileManager:
    def load(self) -> list[SnapshotProfile]:
        try: return [SnapshotProfile.from_dict(d) for d in json.loads(PROFILES_FILE.read_text())]
        except: return []

    def save(self, profiles: list[SnapshotProfile]) -> None:
        SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        tmp = PROFILES_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps([p.to_dict() for p in profiles], indent=2))
        tmp.rename(PROFILES_FILE)

    def add(self, p: SnapshotProfile) -> None:
        ps = self.load(); ps.append(p); self.save(ps)

    def update(self, p: SnapshotProfile) -> None:
        ps = self.load()
        for i,x in enumerate(ps):
            if x.id == p.id: ps[i] = p; break
        self.save(ps)

    def delete(self, pid: str) -> None:
        self.save([p for p in self.load() if p.id != pid])


class SnapshotManager:
    def _set_dir(self, system: str, snap: str) -> Path:
        return SNAPSHOTS_DIR / system / snap

    def _read_meta(self, p: Path) -> dict[str,str]:
        if not p.exists(): return {}
        m: dict[str,str] = {}
        for line in p.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k,_,v = line.partition("=")
                m[k.strip()] = v.strip()
        return m

    def list_sets(self, system: str | None = None) -> list[dict]:
        results: list[dict] = []
        if not SNAPSHOTS_DIR.exists(): return results
        systems = [system] if system else \
                  [d.name for d in SNAPSHOTS_DIR.iterdir() if d.is_dir()]
        for sys_name in systems:
            sd = SNAPSHOTS_DIR / sys_name
            if not sd.is_dir(): continue
            for d in sorted(sd.iterdir(), reverse=True):
                if not d.is_dir(): continue
                m = self._read_meta(d / "snap.meta")
                results.append({
                    "path": d, "name": d.name,
                    "system": m.get("system", sys_name),
                    "rootfs_label": m.get("rootfs_label","?"),
                    "components": m.get("components","?"),
                    "date": m.get("timestamp","?"),
                    "size": dir_size(d),
                    "archived": m.get("archived","false") == "true",
                    "zfs_snap": m.get("zfs_snap_name","?"),
                    "profile": m.get("profile_name","?"),
                    "valid": (d/"snap.meta").exists(),
                })
        return results

    def create(self, profile: SnapshotProfile) -> Generator[str, None, tuple[bool,str]]:
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        snap_name = profile.snap_name(ts)
        set_dir = self._set_dir(profile.system, snap_name)
        set_dir.mkdir(parents=True, exist_ok=True)
        yield f"📸 {snap_name}"

        md5s: dict[str,str] = {}
        sizes: dict[str,str] = {}

        for comp in profile.components:
            ds = profile.dataset_for(comp)
            if not ds or not dataset_exists(ds):
                yield f"  ⚠️  Dataset absent : {ds} — ignoré"
                continue
            yield f"  [{comp}] zfs snapshot {ds}@{snap_name}"
            ok, msg = run(["zfs","snapshot",f"{ds}@{snap_name}"])
            if not ok:
                yield f"  ❌ {msg}"
                import shutil; shutil.rmtree(set_dir, ignore_errors=True)
                return False, f"zfs snapshot {ds} échoué"

            out = set_dir / f"{comp}.zst"
            yield f"  [{comp}] export → {comp}.zst"
            try:
                zfs_p  = subprocess.Popen(["zfs","send",f"{ds}@{snap_name}"],
                                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                zstd_p = subprocess.Popen(["zstd","-T0","-3","-q","-o",str(out)],
                                          stdin=zfs_p.stdout, stderr=subprocess.PIPE)
                zfs_p.stdout.close()  # type: ignore
                _, ze = zstd_p.communicate(); zfs_p.wait()
                if zstd_p.returncode or zfs_p.returncode:
                    yield f"  ❌ export {comp}: {ze.decode().strip()}"
                    import shutil; shutil.rmtree(set_dir, ignore_errors=True)
                    return False, f"export {comp} échoué"
                md5s[comp] = md5file(out)
                sizes[comp] = human_size(out.stat().st_size)
                yield f"  ✅ [{comp}] {sizes[comp]}"
            except Exception as exc:
                yield f"  ❌ {exc}"
                import shutil; shutil.rmtree(set_dir, ignore_errors=True)
                return False, str(exc)

        if not md5s:
            import shutil; shutil.rmtree(set_dir, ignore_errors=True)
            return False, "Aucun composant exporté"

        total = dir_size(set_dir)
        meta = [
            f"# snap.meta {datetime.now().isoformat()}",
            f"snap_name={snap_name}", f"system={profile.system}",
            f"rootfs_label={profile.rootfs_label}",
            f"components={'+'.join(profile.components)}",
            f"timestamp={ts}", f"total_size={total}",
            f"zfs_snap_name={snap_name}",
            f"profile_id={profile.id}", f"profile_name={profile.name}",
            "archived=false", "",
        ] + [f"md5_{c}={m}" for c,m in md5s.items()] \
          + [f"size_{c}={s}" for c,s in sizes.items()]

        tmp = set_dir / "snap.meta.tmp"
        tmp.write_text("\n".join(meta)+"\n"); tmp.rename(set_dir/"snap.meta")
        profile.last_run = datetime.now().isoformat()
        yield f"✅ Set créé : {snap_name}  ({total})"
        return True, snap_name

    def verify(self, snap_path: Path) -> Generator[str, None, tuple[bool,str]]:
        meta = self._read_meta(snap_path/"snap.meta")
        yield f"🔍 {snap_path.name}"
        if not meta: yield "❌ snap.meta manquant"; return False, "meta absent"
        fails = 0
        for comp in meta.get("components","").split("+"):
            if not comp: continue
            f = snap_path / f"{comp}.zst"
            exp = meta.get(f"md5_{comp}","")
            if not f.exists(): yield f"  ❌ {comp}.zst manquant"; fails+=1; continue
            if md5file(f)==exp: yield f"  ✅ {comp}.zst OK"
            else: yield f"  ❌ {comp}.zst MD5 incorrect"; fails+=1
        if fails==0: yield "✅ Valide"; return True, "OK"
        yield f"❌ {fails} erreur(s)"; return False, f"{fails} erreur(s)"

    def restore(self, snap_path: Path) -> Generator[str, None, tuple[bool,str]]:
        meta = self._read_meta(snap_path/"snap.meta")
        yield f"↩️  {snap_path.name}"
        if not meta: yield "❌ snap.meta manquant"; return False, "meta absent"
        system   = meta.get("system","")
        comps    = meta.get("components","").split("+")
        snap_zfs = meta.get("zfs_snap_name","")
        tmp_prof = SnapshotProfile(system=system, components=comps)

        for comp in comps:
            ds = tmp_prof.dataset_for(comp)
            if not ds: continue
            zst = snap_path / f"{comp}.zst"
            if not zst.exists(): yield f"  ❌ {comp}.zst manquant"; return False, f"{comp} absent"

            if snap_zfs:
                ok, _ = run(["zfs","list",f"{ds}@{snap_zfs}"])
            else:
                ok = False

            if ok:
                yield f"  [{comp}] zfs rollback …"
                ok2, msg = run(["zfs","rollback","-r",f"{ds}@{snap_zfs}"])
                if ok2: yield f"  ✅ [{comp}] rollback OK"
                else: yield f"  ❌ rollback: {msg}"; return False, f"rollback {ds} échoué"
            else:
                yield f"  [{comp}] restore depuis .zst …"
                try:
                    zd_p = subprocess.Popen(["zstd","-d",str(zst),"--stdout"], stdout=subprocess.PIPE)
                    rc_p = subprocess.Popen(["zfs","receive","-F",ds], stdin=zd_p.stdout)
                    zd_p.stdout.close()  # type: ignore
                    rc_p.communicate(); zd_p.wait()
                    if rc_p.returncode: yield f"  ❌ zfs receive {ds} échoué"; return False, "receive échoué"
                    yield f"  ✅ [{comp}] restauré"
                except Exception as exc:
                    yield f"  ❌ {exc}"; return False, str(exc)

        yield "✅ Restauration terminée — reboot recommandé"; return True, "OK"

    def prune(self, system: str, keep: int) -> Generator[str, None, tuple[bool,str]]:
        sets = self.list_sets(system)
        yield f"🧹 {system} — garde {keep}, {len(sets)} sets présents"
        if len(sets) <= keep: yield "  Rien à supprimer"; return True, "rien"
        deleted=skipped=0
        for s in sets[keep:]:
            if not s["archived"]:
                yield f"  ⚠️  {s['name']} non archivé — ignoré"; skipped+=1; continue
            snap_zfs = s["zfs_snap"]
            if snap_zfs and snap_zfs!="?":
                comps = s.get("components","").split("+")
                tmp = SnapshotProfile(system=s["system"], components=comps)
                for c in comps:
                    ds = tmp.dataset_for(c)
                    if ds: run(["zfs","destroy",f"{ds}@{snap_zfs}"])
            try:
                import shutil; shutil.rmtree(s["path"])
                yield f"  ✅ {s['name']}"; deleted+=1
            except Exception as exc:
                yield f"  ❌ {s['name']}: {exc}"
        msg = f"{deleted} supprimé(s)"
        if skipped: msg += f", {skipped} ignoré(s)"
        yield f"✅ {msg}"; return True, msg


# =============================================================================
# ÉCRAN : STREAM
# =============================================================================

class StreamScreen(Screen):
    BINDINGS = [Binding("escape","app.pop_screen","Retour")]

    def __init__(self, preset: dict, stream_mgr: StreamManager) -> None:
        super().__init__()
        self._preset = preset
        self._smgr   = stream_mgr

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("📡  STREAM YOUTUBE", classes="screen-title")
        with Horizontal(id="stream-status-bar"):
            yield Static(id="stream-state-label")
            yield Static(id="stream-countdown-label")
        with Horizontal(id="stream-btns"):
            yield Button("▶ Démarrer",   variant="success", id="btn-start")
            yield Button("⏹ Arrêter",    variant="error",   id="btn-stop")
            yield Button("⏸ Annuler CD", variant="warning", id="btn-cancel-cd")
            yield Button("🔙 Retour",    variant="default", id="btn-back")
        with Horizontal(id="stream-config"):
            with Vertical():
                yield Static("Clé stream", classes="field-label")
                yield Input(self._preset.get("stream_key",""), id="f-key",
                            placeholder="xxxx-xxxx-xxxx-xxxx", password=True)
                yield Static("Résolution", classes="field-label")
                yield Select([(r,r) for r in STREAM_RESOLUTIONS],
                             value=self._preset.get("stream_resolution","1920x1080"),
                             id="f-res")
            with Vertical():
                yield Static("FPS", classes="field-label")
                yield Input(str(self._preset.get("stream_fps",30)), id="f-fps")
                yield Static("Bitrate", classes="field-label")
                yield Input(self._preset.get("stream_bitrate","4500k"), id="f-bitrate")
                yield Static("Délai démarrage (sec)", classes="field-label")
                yield Input(str(self._preset.get("stream_delay_sec",30)), id="f-delay")
        yield Button("💾 Sauvegarder la config", variant="primary", id="btn-save-cfg")
        yield Log(id="stream-log", auto_scroll=True)
        yield Footer()

    def on_mount(self) -> None:
        self._update_status()
        self.set_interval(2.0, self._update_status)

    def _update_status(self) -> None:
        state = self._smgr.state()
        cd    = self._smgr.countdown()
        state_w = self.query_one("#stream-state-label", Static)
        cd_w    = self.query_one("#stream-countdown-label", Static)

        colors = {"running":"green","pending":"yellow","stopped":"red",
                  "cancelled":"dim","unknown":"dim"}
        col = colors.get(state, "dim")
        state_w.update(f"[{col}]État : {state}[/{col}]")
        if cd > 0:
            cd_w.update(f"[yellow]Démarrage dans {cd}s[/yellow]")
        else:
            cd_w.update("")

    def _log(self, msg: str) -> None:
        self.query_one("#stream-log", Log).write_line(msg)

    def _save_config_to_preset(self) -> None:
        try:
            self._preset["stream_key"]        = self.query_one("#f-key",     Input).value
            self._preset["stream_resolution"] = getattr(self.query_one("#f-res", Select),"value","1920x1080")
            self._preset["stream_fps"]        = int(self.query_one("#f-fps",     Input).value or "30")
            self._preset["stream_bitrate"]    = self.query_one("#f-bitrate", Input).value or "4500k"
            self._preset["stream_delay_sec"]  = int(self.query_one("#f-delay",   Input).value or "30")
        except Exception as exc:
            self._log(f"Erreur lecture config : {exc}")

    @on(Button.Pressed,"#btn-back")
    def go_back(self) -> None: self.app.pop_screen()

    @on(Button.Pressed,"#btn-start")
    def do_start(self) -> None:
        self._save_config_to_preset()
        ok, msg = self._smgr.start(self._preset)
        self._log(("✅ " if ok else "❌ ") + msg)
        self._update_status()

    @on(Button.Pressed,"#btn-stop")
    def do_stop(self) -> None:
        ok, msg = self._smgr.stop()
        self._log(("✅ " if ok else "❌ ") + msg)
        self._update_status()

    @on(Button.Pressed,"#btn-cancel-cd")
    def do_cancel_cd(self) -> None:
        ok = self._smgr.cancel()
        self._log("✅ Compte à rebours annulé" if ok else "❌ Annulation échouée")
        self._update_status()

    @on(Button.Pressed,"#btn-save-cfg")
    def do_save_cfg(self) -> None:
        self._save_config_to_preset()
        pm = PresetManager()
        if pm.save(self._preset):
            self._log("✅ Configuration stream sauvegardée dans le preset")
        else:
            self._log("❌ Erreur sauvegarde")


# =============================================================================
# ÉCRAN : CONFIGURATION D'UN PRESET
# =============================================================================

class PresetConfigScreen(Screen):
    """Écran de création / modification d'un preset de boot.
    
    Permet de combiner LIBREMENT :
      - Un kernel (kernel-<label>-<date>)          indépendant du rootfs
      - Un initramfs (initramfs-<type>-<date>.img) indépendant du rootfs
      - Des modules optionnels                      indépendants du rootfs
      - Un rootfs optionnel                         (null = preset initial/minimal)
    
    ⚠️  Le rootfs ne contient JAMAIS de kernel ni de modules.
    """
    BINDINGS = [Binding("escape","app.pop_screen","Retour")]

    def __init__(self, preset_mgr: PresetManager,
                 preset: dict | None = None) -> None:
        super().__init__()
        self._pm     = preset_mgr
        self._preset = dict(preset) if preset else {}
        self._is_new = preset is None
        self._kernels: list[ImageInfo] = []
        self._initramfs_list: list[ImageInfo] = []
        self._modules_list: list[ImageInfo] = []
        self._rootfs_list: list[ImageInfo] = []

    def on_mount(self) -> None:
        self._do_load_images()

    @work(thread=True)
    def _do_load_images(self) -> None:
        kernels    = NamingHelper.list_images("kernel")
        initramfs  = NamingHelper.list_images("initramfs")
        modules    = NamingHelper.list_images("modules")
        rootfs     = NamingHelper.list_images("rootfs")
        def update() -> None:
            self._kernels       = kernels
            self._initramfs_list = initramfs
            self._modules_list  = modules
            self._rootfs_list   = rootfs
            self._populate_selects()
        self.app.call_from_thread(update)

    def _img_options(self, imgs: list[ImageInfo], none_label: str = "— aucun —") -> list[tuple[str, str]]:
        opts: list[tuple[str, str]] = [(none_label, "")]
        for img in sorted(imgs, key=lambda i: i.date, reverse=True):
            if img.system == "failsafe":
                continue
            meta = NamingHelper.read_meta(img.path)
            kver = meta.get("kernel_ver", "")
            itype = meta.get("init_type", "")
            sz = img.path.stat().st_size // (1024*1024) if img.path.exists() else 0
            label_str = img.filename
            if kver:   label_str += f"  [kver={kver}]"
            if itype:  label_str += f"  [init={itype}]"
            if sz > 0: label_str += f"  {sz}M"
            opts.append((label_str, str(img.path)))
        return opts

    def compose(self) -> ComposeResult:
        p = self._preset
        title = "➕ Nouveau preset" if self._is_new else f"✏️  {p.get('label', p.get('name','?'))}"
        yield Header(show_clock=True)
        yield Static(title, classes="screen-title")

        with ScrollableContainer():
            with Vertical(id="form"):

                yield Static("─── Identité ───", classes="section-title")
                yield Static("Nom (identifiant, sans espace)", classes="field-label")
                yield Input(p.get("name",""), id="f-name", placeholder="systeme1")

                yield Static("Label affiché dans ZFSBootMenu", classes="field-label")
                yield Input(p.get("label",""), id="f-label",
                            placeholder="Système 1 — Gentoo [préparé]")

                yield Static("Type de preset", classes="field-label")
                yield Select([
                    ("prepared  — Boot complet : TUI Python + stream + overlay", "prepared"),
                    ("normal    — Boot système direct, sans TUI Python",          "normal"),
                    ("stream    — Boot flux vidéo uniquement (init zbm-stream)",  "stream"),
                    ("minimal   — Boot natif noyau, init fourni avec le kernel",  "minimal"),
                ], value=p.get("type","prepared"), id="f-type")

                yield Static("Priorité ZBM (plus petit = affiché en premier)", classes="field-label")
                yield Input(str(p.get("priority",10)), id="f-priority", placeholder="10")

                yield Static("─── Composants de boot ─── (indépendants les uns des autres)", classes="section-title")

                yield Static("⚙️  Kernel  (kernel-<label>-<date>)", classes="field-label")
                kern_opts = self._img_options(self._kernels, "— aucun kernel —")
                cur_k = p.get("kernel","")
                yield Select(kern_opts, value=cur_k, id="f-kernel")

                yield Static("🔧 Initramfs  (initramfs-<type>-<date>.img)", classes="field-label")
                yield Static(
                    "  zbm=TUI+overlay+stream  |  zbm-stream=flux seul  |  minimal=init natif",
                    classes="field-hint"
                )
                init_opts = self._img_options(self._initramfs_list, "— aucun initramfs —")
                cur_i = p.get("initramfs","")
                yield Select(init_opts, value=cur_i, id="f-initramfs")

                yield Static("📦 Modules squashfs  (optionnel)", classes="field-label")
                mod_opts = self._img_options(self._modules_list, "— pas de modules squashfs —")
                cur_m = p.get("modules","") or ""
                yield Select(mod_opts, value=cur_m, id="f-modules")

                yield Static("💿 Rootfs squashfs  (optionnel — null = preset initial ou minimal)", classes="field-label")
                yield Static(
                    "  ⚠️  Le rootfs ne contient JAMAIS de kernel ni de modules.",
                    classes="field-hint"
                )
                rootfs_opts = self._img_options(self._rootfs_list, "— pas de rootfs (boot initial/minimal) —")
                cur_r = p.get("rootfs","") or ""
                yield Select(rootfs_opts, value=cur_r, id="f-rootfs")

                yield Static("─── Mode init-only (rootfs=null) ───", classes="section-title")
                yield Static("Commande exec dans l'initramfs (vide = auto : Python TUI → shell)", classes="field-label")
                yield Static("Ex: /mnt/python/launch.sh  |  /bin/sh  |  /mnt/boot/scripts/setup.sh", classes="field-hint")
                yield Input(p.get("exec",""), id="f-exec", placeholder="(vide = auto)")

                yield Static("─── Datasets ZFS (remplis automatiquement si rootfs choisi) ───", classes="section-title")

                yield Static("Dataset overlay (OverlayFS upper partagé)", classes="field-label")
                yield Input(p.get("overlay_dataset",""), id="f-overlay",
                            placeholder="fast_pool/overlay-systeme1")

                yield Static(
                    "ℹ /var /tmp → upper overlay (fast_pool/overlay-<s>). Aucun dataset séparé.",
                    classes="field-hint"
                )

                yield Static("─── Stream ───", classes="section-title")
                yield Static("Clé stream YouTube (vide = pas de stream)", classes="field-label")
                yield Input(p.get("stream_key",""), id="f-stream-key", password=True)

                yield Static("Résolution", classes="field-label")
                yield Input(p.get("stream_resolution","1920x1080"), id="f-res")

                yield Static("FPS", classes="field-label")
                yield Input(str(p.get("stream_fps",30)), id="f-fps")

                yield Static("─── Réseau ───", classes="section-title")
                yield Static("Mode réseau", classes="field-label")
                yield Select([
                    ("DHCP automatique", "dhcp"),
                    ("Statique (configurer ci-dessous)", "static"),
                    ("Désactivé", "none"),
                ], value=p.get("network_mode","dhcp"), id="f-net-mode")

                yield Static("", classes="spacer")
                with Horizontal():
                    yield Button("💾 Sauvegarder", variant="success", id="btn-save")
                    yield Button("🔍 Vérifier",    variant="primary",  id="btn-check")
                    yield Button("❌ Annuler",     variant="error",    id="btn-cancel")

        yield Footer()

    def _collect(self) -> dict:
        def val(wid_id: str) -> str:
            try: return self.query_one(f"#{wid_id}", Input).value.strip()
            except: return ""
        def sel(wid_id: str, default: str = "") -> str:
            try: v = self.query_one(f"#{wid_id}", Select).value; return str(v) if v else default
            except: return default

        p = dict(self._preset)
        p["name"]             = val("f-name")
        p["label"]            = val("f-label")
        p["type"]             = sel("f-type", "prepared")
        p["priority"]         = int(val("f-priority") or "10")
        p["kernel"]           = sel("f-kernel")
        p["initramfs"]        = sel("f-initramfs")
        p["modules"]          = sel("f-modules") or None
        p["rootfs"]           = sel("f-rootfs") or None
        p["exec"]             = val("f-exec") or ""
        p["overlay_dataset"]  = val("f-overlay") or None
        # var_dataset / log_dataset / tmp_dataset : supprimés (architecture overlay)
        p["stream_key"]       = val("f-stream-key")
        p["stream_resolution"] = val("f-res") or "1920x1080"
        p["stream_fps"]       = int(val("f-fps") or "30")
        p["network_mode"]     = sel("f-net-mode", "dhcp")

        # Init type depuis le fichier initramfs sélectionné
        if p.get("initramfs"):
            i_img = NamingHelper.parse(Path(p["initramfs"]))
            if i_img:
                meta = NamingHelper.read_meta(Path(p["initramfs"]))
                p["init_type"] = meta.get("init_type", i_img.label)

        # Auto-remplir datasets depuis le rootfs sélectionné
        if p.get("rootfs"):
            r_img = NamingHelper.parse(Path(p["rootfs"]))
            if r_img and r_img.system and not p.get("overlay_dataset"):
                # Architecture overlay : seul l'overlay-<s> est un dataset ZFS
                p["overlay_dataset"] = f"fast_pool/overlay-{r_img.system}"

        # Cmdline — ordre canonique : system rootfs modules overlay var log tmp
        if p.get("kernel") and p.get("initramfs"):
            r_img = NamingHelper.parse(Path(p["rootfs"])) if p.get("rootfs") else None
            system_name = r_img.system if r_img else p["name"]
            p["cmdline"] = "quiet loglevel=3"
            p["cmdline"] += f" zbm_system={system_name}"
            if p.get("rootfs") and p["rootfs"] != "null":
                p["cmdline"] += f" zbm_rootfs={p['rootfs']}"
            else:
                p["cmdline"] += " zbm_rootfs=none"
                if p.get("exec") and p["exec"] not in ("", "none"):
                    p["cmdline"] += f" zbm_exec={p['exec']}"
            if p.get("modules"):
                p["cmdline"] += f" zbm_modules={p['modules']}"
            if r_img and r_img.system:
                s = r_img.system
                # Overlay PAR SYSTÈME — jamais fast_pool/overlay générique
                p["overlay_dataset"] = p.get("overlay_dataset") or f"fast_pool/overlay-{s}"
                # var/log/tmp_dataset supprimés
                p["cmdline"] += f" zbm_overlay={p['overlay_dataset']}"
        # Meta kernel
        if p.get("kernel"):
            meta = NamingHelper.read_meta(Path(p["kernel"]))
            p["_kernel_ver"] = meta.get("kernel_ver", "")

        return p

    def _check_preset(self, p: dict) -> list[str]:
        """Vérifie la cohérence du preset avant sauvegarde."""
        issues = []
        if not p.get("name"):
            issues.append("❌ Nom obligatoire")
        if not p.get("kernel"):
            issues.append("❌ Kernel obligatoire")
        elif not Path(p["kernel"]).exists():
            issues.append(f"❌ Kernel introuvable : {p['kernel']}")
        if not p.get("initramfs"):
            issues.append("❌ Initramfs obligatoire")
        elif not Path(p["initramfs"]).exists():
            issues.append(f"❌ Initramfs introuvable : {p['initramfs']}")
        if p.get("modules") and not Path(p["modules"]).exists():
            issues.append(f"⚠ Modules introuvables : {p['modules']}")
        if p.get("rootfs") and p["rootfs"] != "null" and not Path(p["rootfs"]).exists():
            issues.append(f"⚠ Rootfs introuvable : {p['rootfs']}")
        if p.get("rootfs") and p["rootfs"] != "null":
            r_img = NamingHelper.parse(Path(p["rootfs"]))
            if not r_img:
                issues.append("⚠ Rootfs : nom hors convention")
        # Type/init cohérence
        ptype = p.get("type","")
        itype = p.get("init_type","")
        if ptype == "stream" and itype != "zbm-stream":
            issues.append("⚠ Type stream → utiliser un initramfs de type zbm-stream")
        if ptype == "minimal" and itype not in ("minimal",""):
            issues.append("⚠ Type minimal → préférer un initramfs minimal")
        # Validation cmdline ZBM
        cmdline = p.get("cmdline", "")
        if cmdline:
            # zbm_rootfs doit être présent si rootfs défini
            rootfs = p.get("rootfs")
            if rootfs and rootfs != "null":
                if "zbm_rootfs=" not in cmdline:
                    issues.append("⚠ cmdline : zbm_rootfs= absent alors qu'un rootfs est défini")
            # zbm_rootfs=none uniquement si init-only
            if "zbm_rootfs=none" in cmdline and rootfs and rootfs != "null":
                issues.append("❌ cmdline : zbm_rootfs=none incompatible avec un rootfs")
            # Paramètres ZBM reconnus
            known_zbm = {"zbm_rootfs", "zbm_modules", "zbm_system",
                         "zbm.timeout", "zbm.prefer", "zbm.skip",
                         "loglevel", "quiet", "ro", "rw"}
            for token in cmdline.split():
                key = token.split("=")[0]
                if key.startswith("zbm") and key not in known_zbm:
                    issues.append(f"⚠ cmdline : paramètre ZBM inconnu : {key}")
        return issues

    @on(Button.Pressed,"#btn-check")
    def do_check(self) -> None:
        p = self._collect()
        issues = self._check_preset(p)
        if issues:
            msg = "\n".join(issues)
            self.notify(msg, severity="warning", timeout=8)
        else:
            self.notify("✅ Preset valide", severity="information")

    @on(Button.Pressed,"#btn-cancel")
    def do_cancel(self) -> None: self.app.pop_screen()

    @on(Button.Pressed,"#btn-save")
    def do_save(self) -> None:
        p = self._collect()
        issues = self._check_preset(p)
        # Bloquer si erreurs critiques (❌)
        critical = [i for i in issues if i.startswith("❌")]
        if critical:
            self.notify("\n".join(critical), severity="error"); return
        # Avertir si avertissements mais permettre
        warnings = [i for i in issues if i.startswith("⚠")]
        if warnings:
            self.notify("⚠ " + " | ".join(warnings), severity="warning", timeout=5)

        if self._is_new:
            p["_file"] = str(PRESETS_DIR / f"{p['name']}.json")
        if self._pm.save(p):
            self.notify(f"✅ Preset '{p['name']}' sauvegardé")
            self.app.pop_screen()
        else:
            self.notify("❌ Erreur sauvegarde", severity="error")

    @on(Select.Changed, "#f-rootfs")
    def on_rootfs_changed(self, event: Select.Changed) -> None:
        """Auto-remplir les datasets quand un rootfs est sélectionné."""
        val = str(event.value) if event.value else ""
        if not val:
            return
        r_img = NamingHelper.parse(Path(val))
        if r_img and r_img.system:
            try:
                self.query_one("#f-overlay", Input).value = f"fast_pool/overlay-{r_img.system}"
                # var/log/tmp supprimés : architecture overlay
            except Exception:
                pass
            self.notify(f"Datasets auto-remplis pour {r_img.system}")


# =============================================================================
# ÉCRAN : SNAPSHOTS
# =============================================================================

class ProfileEditScreen(Screen):
    BINDINGS = [Binding("escape","app.pop_screen","Retour")]

    def __init__(self, pmgr: ProfileManager, premgr: PresetManager,
                 profile: SnapshotProfile | None = None) -> None:
        super().__init__()
        self._pmgr   = pmgr
        self._premgr = premgr
        self._p      = profile or SnapshotProfile()
        self._is_new = profile is None

    def compose(self) -> ComposeResult:
        p = self._p
        yield Header(show_clock=True)
        yield Static("Profil de snapshot", classes="screen-title")
        with ScrollableContainer():
            with Vertical(id="form"):
                yield Static("Nom du profil", classes="field-label")
                yield Input(p.name, id="f-name", placeholder="systeme1 quotidien var+log")
                yield Static("Système", classes="field-label")
                # Charger la liste des systèmes depuis config.sh (source de vérité)
                # puis compléter avec les noms de presets non-failsafe
                _sys_cfg = available_systems()
                _sys_presets = [s.get("name","?") for s in self._premgr.load()
                                if not s.get("protected") and s.get("name") not in ("initial","failsafe")]
                _all_sys = _sys_cfg + [s for s in _sys_presets if s not in _sys_cfg]
                systems = [(s, s) for s in _all_sys if s]
                if not systems: systems = [("systeme1","systeme1")]
                yield Select(options=systems, value=p.system, id="f-sys")
                yield Static("Label rootfs", classes="field-label")
                yield Input(p.rootfs_label, id="f-rl", placeholder="gentoo-6.19")
                yield Static("Composants", classes="field-label")
                yield Static("[dim]ovl=diff rootfs · var=/var · log=/var/log · tmp=/tmp[/dim]")
                with Horizontal():
                    for cid, cdesc in COMPONENTS.items():
                        yield Checkbox(f"{cid} — {cdesc}", value=cid in p.components,
                                       id=f"comp-{cid}")
                yield Static("Planification", classes="field-label")
                yield Select([(s.capitalize(),s) for s in SCHEDULES],
                             value=p.schedule, id="f-sched")
                yield Static("Heure (0-23)", classes="field-label")
                yield Input(str(p.schedule_hour), id="f-hour")
                yield Static("Rétention (nb de sets)", classes="field-label")
                yield Input(str(p.retention), id="f-ret")
                yield Static("Aperçu du nom :", classes="field-label")
                yield Static(id="preview", classes="snap-preview")
                with Horizontal():
                    yield Button("💾 Sauvegarder", variant="success", id="btn-save")
                    yield Button("❌ Annuler",     variant="error",   id="btn-cancel")
        yield Footer()

    def on_mount(self) -> None: self._update_preview()

    def _comps(self) -> list[str]:
        return [c for c in COMPONENTS
                if self.query_one(f"#comp-{c}", Checkbox).value]

    def _update_preview(self) -> None:
        try:
            sys_v  = getattr(self.query_one("#f-sys",  Select),"value",self._p.system)
            rl_v   = self.query_one("#f-rl",  Input).value
            comps  = self._comps() or ["?"]
            tmp = SnapshotProfile(system=sys_v or "sys", rootfs_label=rl_v or "rootfs",
                                  components=comps)
            self.query_one("#preview", Static).update(
                f"[bold cyan]{tmp.snap_name('20250305-143022')}[/bold cyan]")
        except: pass

    @on(Input.Changed)
    def _oc(self,_: Input.Changed) -> None: self._update_preview()
    @on(Checkbox.Changed)
    def _och(self,_: Checkbox.Changed) -> None: self._update_preview()
    @on(Select.Changed)
    def _os(self,_: Select.Changed) -> None: self._update_preview()
    @on(Button.Pressed,"#btn-cancel")
    def do_cancel(self) -> None: self.app.pop_screen()

    @on(Button.Pressed,"#btn-save")
    def do_save(self) -> None:
        name = self.query_one("#f-name",Input).value.strip()
        comps = self._comps()
        if not name: self.notify("Nom obligatoire",severity="error"); return
        if not comps: self.notify("Sélectionnez un composant",severity="error"); return
        try:
            hour = int(self.query_one("#f-hour",Input).value or "2")
            ret  = int(self.query_one("#f-ret", Input).value or "7")
        except ValueError:
            self.notify("Heure et rétention doivent être des entiers",severity="error"); return
        self._p.name          = name
        self._p.system        = getattr(self.query_one("#f-sys",  Select),"value",self._p.system) or self._p.system
        self._p.rootfs_label  = self.query_one("#f-rl", Input).value
        self._p.components    = comps
        self._p.schedule      = getattr(self.query_one("#f-sched",Select),"value","none") or "none"
        self._p.schedule_hour = max(0,min(23,hour))
        self._p.retention     = max(1,ret)
        if self._is_new: self._pmgr.add(self._p)
        else:            self._pmgr.update(self._p)
        self.notify(f"Profil '{name}' sauvegardé")
        self.app.pop_screen()


class SnapshotScreen(Screen):
    BINDINGS = [Binding("escape","app.pop_screen","Retour")]

    def __init__(self, smgr: SnapshotManager, pmgr: ProfileManager,
                 premgr: PresetManager, system: str | None = None) -> None:
        super().__init__()
        self._smgr  = smgr; self._pmgr = pmgr
        self._premgr = premgr; self._system = system

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static(f"📸  SNAPSHOTS — {self._system or 'tous'}", classes="screen-title")
        with Horizontal(id="snap-layout"):
            with Vertical(id="snap-left"):
                yield Static("Profils", classes="panel-title")
                yield ListView(id="profile-list")
                with Horizontal():
                    yield Button("➕",variant="success",id="btn-np",tooltip="Nouveau profil")
                    yield Button("✏️", variant="warning",id="btn-ep",tooltip="Modifier")
                    yield Button("🗑️", variant="error",  id="btn-dp",tooltip="Supprimer")
                    yield Button("▶", variant="primary", id="btn-rp",tooltip="Exécuter")
            with Vertical(id="snap-right"):
                yield Static("Sets", classes="panel-title")
                yield DataTable(id="sets-table", cursor_type="row")
                with Horizontal():
                    yield Button("↩️  Restaurer",variant="warning",id="btn-restore")
                    yield Button("✅ Vérifier", variant="primary", id="btn-verify")
                    yield Button("🧹 Nettoyer", variant="error",   id="btn-prune")
                yield Log(id="snap-log", auto_scroll=True)
        yield Button("🔙 Retour",variant="default",id="btn-back")
        yield Footer()

    def on_mount(self) -> None:
        t = self.query_one("#sets-table",DataTable)
        t.add_columns("Snapshot","Composants","Taille","Date","Archivé")
        self._reload_profiles()

    def _reload_profiles(self) -> None:
        lv = self.query_one("#profile-list",ListView); lv.clear()
        profiles = self._pmgr.load()
        if self._system: profiles = [p for p in profiles if p.system==self._system]
        for p in profiles:
            sc = f"  [{p.schedule}]" if p.schedule!="none" else ""
            lv.append(ListItem(Label(f"{p.name}\n[dim]{p.system}·{'+'.join(p.components)}{sc}[/dim]"),
                               name=p.id))

    def _reload_sets(self, profile: SnapshotProfile | None = None) -> None:
        t = self.query_one("#sets-table",DataTable); t.clear()
        sys = profile.system if profile else self._system
        sets = self._smgr.list_sets(sys)
        if profile:
            sets = [s for s in sets if s.get("profile")==profile.name]
        for s in sets:
            t.add_row(s["name"],s["components"],s["size"],s["date"],
                      "✅" if s["archived"] else "❌", key=str(s["path"]))

    def _sel_prof(self) -> SnapshotProfile | None:
        lv = self.query_one("#profile-list",ListView)
        if lv.index is None: return None
        item = lv.highlighted_child
        for p in self._pmgr.load():
            if p.id == item.name: return p  # type: ignore
        return None

    def _sel_set(self) -> Path | None:
        t = self.query_one("#sets-table",DataTable)
        try:
            rk = t.coordinate_to_cell_key(Coordinate(t.cursor_coordinate.row,0)).row_key
            return Path(str(rk.value)) if rk.value else None
        except: return None

    def _run_gen(self, gen: Generator, reload: bool = True) -> None:
        self._run_snap_worker(gen, reload)

    @work(thread=True)
    def _run_snap_worker(self, gen: Generator, reload: bool = True) -> None:
        log = self.query_one("#snap-log", Log)
        self.app.call_from_thread(log.clear)
        def w(line: str) -> None:
            self.app.call_from_thread(log.write_line, line)
        result = None
        try:
            while True: w(next(gen))
        except StopIteration as e: result = e.value
        if result:
            ok2, detail = result
            w(f"\n{'✅' if ok2 else '❌'}  {detail}")
            if ok2 and reload:
                self.app.call_from_thread(lambda: self._reload_sets(self._sel_prof()))

    @on(ListView.Selected,"#profile-list")
    def _ps(self,_: ListView.Selected) -> None: self._reload_sets(self._sel_prof())
    @on(Button.Pressed,"#btn-back")
    def go_back(self) -> None: self.app.pop_screen()
    @on(Button.Pressed,"#btn-np")
    def do_new_p(self) -> None:
        self.app.push_screen(ProfileEditScreen(self._pmgr,self._premgr),
                             callback=lambda _: self._reload_profiles())
    @on(Button.Pressed,"#btn-ep")
    def do_edit_p(self) -> None:
        p = self._sel_prof()
        if not p: self.notify("Sélectionnez un profil",severity="warning"); return
        self.app.push_screen(ProfileEditScreen(self._pmgr,self._premgr,p),
                             callback=lambda _: self._reload_profiles())
    @on(Button.Pressed,"#btn-dp")
    def do_del_p(self) -> None:
        p = self._sel_prof()
        if not p: return
        self._pmgr.delete(p.id); self._reload_profiles()
        self.query_one("#sets-table",DataTable).clear()
    @on(Button.Pressed,"#btn-rp")
    def do_run_p(self) -> None:
        p = self._sel_prof()
        if not p: self.notify("Sélectionnez un profil",severity="warning"); return
        self._run_gen(self._smgr.create(p)); self._pmgr.update(p)
    @on(Button.Pressed,"#btn-restore")
    def do_restore(self) -> None:
        path = self._sel_set()
        if not path: self.notify("Sélectionnez un set",severity="warning"); return
        self._run_gen(self._smgr.restore(path), reload=False)
    @on(Button.Pressed,"#btn-verify")
    def do_verify(self) -> None:
        path = self._sel_set()
        if not path: self.notify("Sélectionnez un set",severity="warning"); return
        self._run_gen(self._smgr.verify(path), reload=False)
    @on(Button.Pressed,"#btn-prune")
    def do_prune(self) -> None:
        p = self._sel_prof()
        if not p: self.notify("Sélectionnez un profil",severity="warning"); return
        self._run_gen(self._smgr.prune(p.system, p.retention))


# =============================================================================
# HOT-SWAP MANAGER
# =============================================================================

class HotSwapManager:
    """
    Changement à chaud de kernel / modules / rootfs.

    ─── Kernel ───────────────────────────────────────────────────────────────
    Utilise kexec pour charger un nouveau kernel en mémoire puis l'exécuter.
    Le nouveau kernel remplace le kernel en cours SANS cycle POST/UEFI.
    Commande : kexec -l <vmlinuz> --initrd=<initrd> --command-line=<cmdline>
               kexec -e

    ─── Modules ──────────────────────────────────────────────────────────────
    Deux modes :
      1. modprobe <module>       : charge un module depuis le système en cours
      2. Remplacer modules.sfs   : démonte l'ancien loop, monte le nouveau
         (prend effet sur les modules chargés à partir de ce moment)

    ─── Rootfs ───────────────────────────────────────────────────────────────
    Change le symlink $BOOT/rootfs.sfs.
    Prend effet au prochain kexec ou reboot (le rootfs est monté en init).
    Option : enchaîner avec un kexec immédiat pour appliquer sans reboot POST.
    """

    def list_kernels(self) -> list[Path]:
        """Liste les kernels disponibles — convention kernel-<s>-<lbl>-<date>"""
        imgs = NamingHelper.list_images("kernel")
        return sorted([i.path for i in imgs], key=lambda p: p.name)

    def list_initramfs(self) -> list[Path]:
        imgs = NamingHelper.list_images("initramfs")
        return sorted([i.path for i in imgs], key=lambda p: p.name)

    def list_modules_sfs(self) -> list[Path]:
        imgs = NamingHelper.list_images("modules")
        return sorted([i.path for i in imgs], key=lambda p: p.name)

    def list_rootfs_sfs(self) -> list[Path]:
        imgs = NamingHelper.list_images("rootfs")
        return sorted([i.path for i in imgs], key=lambda p: p.name)

    def current_kernel(self) -> str:
        link = BOOT / "boot" / "vmlinuz"
        return readlink(link) if link.is_symlink() else "—"

    def current_rootfs(self) -> str:
        link = BOOT / "boot" / "rootfs.sfs"
        return readlink(link) if link.is_symlink() else "—"

    def current_modules(self) -> str:
        link = BOOT / "boot" / "modules.sfs"
        if link.is_symlink():
            return readlink(link)
        try:
            ok2, out = run(["findmnt", "-n", "-o", "SOURCE", "/mnt/modloop"])
            return out.strip() if ok2 else "—"
        except:
            return "—"

    # ── Kernel hot-swap via kexec ──────────────────────────────────────────

    def kexec_load(
        self, kernel: Path, initrd: Path, cmdline: str
    ) -> Generator[str, None, tuple[bool, str]]:
        yield f"🔄 Chargement kexec : {kernel.name}"
        yield f"   initrd  : {initrd.name}"
        yield f"   cmdline : {cmdline[:80]}{'…' if len(cmdline)>80 else ''}"

        if not kernel.exists():
            yield f"❌ Kernel introuvable : {kernel}"
            return False, "kernel absent"
        if not initrd.exists():
            yield f"❌ Initrd introuvable : {initrd}"
            return False, "initrd absent"
        if not Path("/sbin/kexec").exists() and not Path("/usr/sbin/kexec").exists():
            yield "❌ kexec non disponible (apt install kexec-tools dans le rootfs)"
            return False, "kexec absent"

        ok, msg = run([
            "kexec", "-l", str(kernel),
            f"--initrd={initrd}",
            f"--command-line={cmdline}",
        ])
        if ok:
            yield "✅ Kernel chargé en mémoire — prêt pour kexec -e"
            return True, "kernel chargé"
        yield f"❌ kexec -l échoué : {msg}"
        return False, msg

    def kexec_exec(self) -> tuple[bool, str]:
        """Exécute le kernel précédemment chargé. Ne retourne pas si succès."""
        ok, msg = run(["kexec", "-e"])
        return ok, msg  # ne devrait pas atteindre ce point si succès

    # ── Modules hot-swap ──────────────────────────────────────────────────

    def load_module(self, module: str) -> Generator[str, None, tuple[bool, str]]:
        yield f"📦 modprobe {module}"
        ok, msg = run(["modprobe", module])
        if ok:
            yield f"✅ Module {module} chargé"
            return True, f"{module} chargé"
        yield f"❌ {msg}"
        return False, msg

    def swap_modules_sfs(
        self, new_sfs: Path
    ) -> Generator[str, None, tuple[bool, str]]:
        yield f"📦 Remplacement modules.sfs → {new_sfs.name}"

        if not new_sfs.exists():
            yield f"❌ Fichier introuvable : {new_sfs}"
            return False, "fichier absent"

        # Démonter l'ancien modloop si monté
        mnt = Path("/mnt/modloop")
        if mnt.is_mount():
            yield "   Démontage ancien modules.sfs…"
            ok2, msg2 = run(["umount", "-l", str(mnt)])
            if not ok2:
                yield f"   ⚠️  umount : {msg2}"

        mnt.mkdir(parents=True, exist_ok=True)
        ok2, msg2 = run(["mount", "-t", "squashfs", "-o", "loop,ro",
                         str(new_sfs), str(mnt)])
        if ok2:
            yield f"✅ {new_sfs.name} monté sur /mnt/modloop"
            # Mettre à jour le symlink modules dans $BOOT si besoin
            link = BOOT / "boot" / "modules.sfs"
            try:
                link.unlink(missing_ok=True)
                link.symlink_to(str(new_sfs))
            except Exception:
                pass
            return True, f"{new_sfs.name} monté"
        yield f"❌ mount : {msg2}"
        return False, msg2

    # ── Rootfs hot-swap ───────────────────────────────────────────────────

    def swap_rootfs(
        self, new_sfs: Path, kexec_now: bool,
        kernel: Path | None, initrd: Path | None, cmdline: str
    ) -> Generator[str, None, tuple[bool, str]]:
        yield f"🔀 Changement rootfs → {new_sfs.name}"

        if not new_sfs.exists():
            yield f"❌ Fichier introuvable : {new_sfs}"
            return False, "fichier absent"

        # Mettre à jour le symlink $BOOT/rootfs.sfs
        link = BOOT / "boot" / "rootfs.sfs"
        try:
            link.unlink(missing_ok=True)
            link.symlink_to(str(new_sfs))
            yield f"✅ Symlink mis à jour : rootfs.sfs → {new_sfs}"
        except Exception as exc:
            yield f"❌ Symlink : {exc}"
            return False, str(exc)

        if not kexec_now:
            yield "ℹ️  Le nouveau rootfs sera actif au prochain boot"
            return True, "symlink mis à jour"

        # kexec pour appliquer immédiatement
        if not kernel or not initrd:
            yield "⚠️  kexec demandé mais kernel/initrd non spécifiés"
            return True, "symlink mis à jour (kexec ignoré)"

        yield ""
        gen = self.kexec_load(kernel, initrd, cmdline)
        result = None
        try:
            while True: yield next(gen)
        except StopIteration as e: result = e.value

        if result and result[0]:
            yield ""
            yield "⚡ Exécution kexec dans 3 secondes…"
            import time; time.sleep(3)
            self.kexec_exec()
            return True, "kexec exécuté"
        return False, "kexec load échoué"


# =============================================================================
# ÉCRAN : HOT-SWAP
# =============================================================================

class HotSwapScreen(Screen):
    BINDINGS = [Binding("escape", "app.pop_screen", "Retour")]

    def __init__(self, preset_mgr: PresetManager) -> None:
        super().__init__()
        self._pm   = preset_mgr
        self._hsmgr = HotSwapManager()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("🔀  HOT-SWAP  (kernel / modules / rootfs)", classes="screen-title")

        with Horizontal(id="hs-layout"):
            # Colonne gauche : listes
            with Vertical(id="hs-left"):
                yield Static("Kernels disponibles", classes="panel-title")
                yield ListView(id="kernel-list")
                yield Static("Initramfs disponibles", classes="panel-title")
                yield ListView(id="initrd-list")
                yield Static("Modules .sfs", classes="panel-title")
                yield ListView(id="modules-list")
                yield Static("Rootfs .sfs", classes="panel-title")
                yield ListView(id="rootfs-list")

            # Colonne droite : actions et log
            with Vertical(id="hs-right"):
                # État actuel
                yield Static(id="hs-current", classes="hs-current")

                # Cmdline pour kexec
                yield Static("Cmdline kexec (auto-remplie depuis le preset actif)", classes="field-label")
                yield Input(id="hs-cmdline", placeholder="quiet zbm_system=systeme1 …")

                # Boutons kernel
                yield Static("─── Kernel ───────────────────────────────", classes="section-sep")
                with Horizontal():
                    yield Button("📥 kexec load",  variant="warning", id="btn-kexec-load",
                                 tooltip="Charge le kernel sélectionné en mémoire")
                    yield Button("⚡ kexec exec",  variant="error",   id="btn-kexec-exec",
                                 tooltip="Exécute le kernel chargé (sans POST)")

                # Boutons modules
                yield Static("─── Modules ──────────────────────────────", classes="section-sep")
                with Horizontal():
                    yield Button("📦 Monter .sfs",  variant="primary", id="btn-swap-modules",
                                 tooltip="Monte le modules.sfs sélectionné sur /mnt/modloop")
                    yield Input(id="hs-modprobe", placeholder="nom_module (modprobe direct)")
                    yield Button("▶ modprobe",     variant="default", id="btn-modprobe")

                # Boutons rootfs
                yield Static("─── Rootfs ───────────────────────────────", classes="section-sep")
                with Horizontal():
                    yield Button("🔀 Changer symlink", variant="primary",  id="btn-swap-rootfs",
                                 tooltip="Change rootfs.sfs (actif au prochain boot)")
                    yield Button("🔀+⚡ Swap + kexec",  variant="error",   id="btn-swap-kexec",
                                 tooltip="Change rootfs.sfs ET kexec immédiatement")
                    yield Button("🔙 Retour",          variant="default",  id="btn-back")

                yield Log(id="hs-log", auto_scroll=True)

        yield Footer()

    def on_mount(self) -> None:
        self._do_hs_init()

    @work(thread=True)
    def _do_hs_init(self) -> None:
        # Collecte bloquante hors event loop
        kernels   = self._hsmgr.list_kernels()
        initramfs = self._hsmgr.list_initramfs()
        modules   = self._hsmgr.list_modules_sfs()
        rootfs    = self._hsmgr.list_rootfs_sfs()
        cur_k = self._hsmgr.current_kernel()
        cur_m = self._hsmgr.current_modules()
        cur_r = self._hsmgr.current_rootfs()
        def update() -> None:
            self._fill_list("kernel-list",  kernels,   cur_k)
            self._fill_list("initrd-list",  initramfs, "")
            self._fill_list("modules-list", modules,   cur_m)
            self._fill_list("rootfs-list",  rootfs,    cur_r)
            self._update_current_static(cur_k, cur_r, cur_m)
            self._prefill_cmdline()
        self.app.call_from_thread(update)

    def _reload_lists(self) -> None:
        """Remplit les listes de composants disponibles (thread-safe)."""
        self._do_hs_init()

    def _fill_list(self, list_id: str, paths: list[Path], current_marker: str = "") -> None:
        """Remplissage d'une ListView — appelé depuis call_from_thread."""
        lv = self.query_one(f"#{list_id}", ListView)
        lv.clear()
        for p in sorted(paths, key=lambda x: x.name, reverse=True):
            size = f" ({human_size(p.stat().st_size)})" if p.exists() else ""
            is_active = bool(current_marker and (
                p.name in current_marker or current_marker.endswith(p.name)
            ))
            marker = " [cyan]◀ actif[/cyan]" if is_active else ""
            img = NamingHelper.parse(p)
            meta = NamingHelper.read_meta(p) if img else {}
            extra = ""
            if img:
                kv = meta.get("kernel_ver","")
                it = meta.get("init_type","")
                if img.type_ in ("kernel","modules"):
                    extra = f" [dim]{img.label}/{img.date}"
                    if kv: extra += f" k={kv}"
                    extra += "[/dim]"
                elif img.type_ == "initramfs":
                    extra = f" [dim]{img.label}/{img.date}"
                    if it: extra += f" [{it}]"
                    extra += "[/dim]"
                elif img.type_ == "rootfs":
                    extra = f" [dim]{img.system}/{img.label}/{img.date}[/dim]"
            lv.append(ListItem(Label(f"{p.name}{size}{marker}{extra}"), name=str(p)))

    def _update_current(self) -> None:
        """Lance la mise à jour dans un thread (lecture symlinks)."""
        self._do_update_current()

    @work(thread=True)
    def _do_update_current(self) -> None:
        cur_k = self._hsmgr.current_kernel()
        cur_r = self._hsmgr.current_rootfs()
        cur_m = self._hsmgr.current_modules()
        self.app.call_from_thread(self._update_current_static, cur_k, cur_r, cur_m)

    def _update_current_static(self, cur_k: str, cur_r: str, cur_m: str) -> None:
        lines = [
            "[bold]État actuel[/bold]",
            f"  kernel  : {cur_k}",
            f"  rootfs  : {cur_r}",
            f"  modules : {cur_m}",
        ]
        self.query_one("#hs-current", Static).update("\n".join(lines))

    def _prefill_cmdline(self) -> None:
        """Pré-remplir la cmdline depuis le preset actif."""
        active = self._pm.active_name()
        if active:
            for p in self._pm.load():
                if p.get("name") == active:
                    cmdline = p.get("cmdline", "")
                    self.query_one("#hs-cmdline", Input).value = cmdline
                    break

    def _sel(self, list_id: str) -> Path | None:
        lv = self.query_one(f"#{list_id}", ListView)
        if lv.index is None: return None
        try:
            item = lv.highlighted_child
            return Path(item.name)  # type: ignore
        except: return None

    def _log(self, msg: str) -> None:
        self.query_one("#hs-log", Log).write_line(msg)

    @on(Button.Pressed, "#btn-back")
    def go_back(self) -> None: self.app.pop_screen()

    @on(Button.Pressed, "#btn-kexec-load")
    def do_kexec_load(self) -> None:
        kernel = self._sel("kernel-list")
        initrd = self._sel("initrd-list")
        cmdline = self.query_one("#hs-cmdline", Input).value.strip()
        if not kernel:
            self._log("⚠️  Sélectionnez un kernel"); return
        if not initrd:
            kver = re.sub(r'^vmlinuz-', '', kernel.name)
            candidates = list((BOOT/"images"/"initramfs").glob(f"initramfs-{kver}*.img"))
            if candidates:
                initrd = candidates[0]
                self._log(f"Auto-sélection initrd : {initrd.name}")
            else:
                self._log("⚠️  Sélectionnez un initrd dans la liste"); return
        if not cmdline:
            cmdline = f"quiet zbm_system={current_system() or available_systems()[0]}"
        self._run_gen_worker(self._hsmgr.kexec_load(kernel, initrd, cmdline), reload=False)

    @on(Button.Pressed, "#btn-kexec-exec")
    def do_kexec_exec(self) -> None:
        self._log("⚡ Exécution kexec… le système va redémarrer")
        ok, msg = self._hsmgr.kexec_exec()
        self._log(f"❌ kexec -e : {msg}")

    @on(Button.Pressed, "#btn-swap-modules")
    def do_swap_modules(self) -> None:
        sfs = self._sel("modules-list")
        if not sfs: self._log("⚠️  Sélectionnez un modules.sfs"); return
        self._run_gen_worker(self._hsmgr.swap_modules_sfs(sfs), reload=True)

    @on(Button.Pressed, "#btn-modprobe")
    def do_modprobe(self) -> None:
        mod = self.query_one("#hs-modprobe", Input).value.strip()
        if not mod: self._log("⚠️  Entrez un nom de module"); return
        self._run_gen_worker(self._hsmgr.load_module(mod), reload=False)

    @on(Button.Pressed, "#btn-swap-rootfs")
    def do_swap_rootfs(self) -> None:
        sfs = self._sel("rootfs-list")
        if not sfs: self._log("⚠️  Sélectionnez un rootfs.sfs"); return
        self._run_gen_worker(
            self._hsmgr.swap_rootfs(sfs, kexec_now=False, kernel=None, initrd=None, cmdline=""),
            reload=True
        )

    @on(Button.Pressed, "#btn-swap-kexec")
    def do_swap_kexec(self) -> None:
        sfs    = self._sel("rootfs-list")
        kernel = self._sel("kernel-list")
        initrd = self._sel("initrd-list")
        cmdline = self.query_one("#hs-cmdline", Input).value.strip()
        if not sfs:    self._log("⚠️  Sélectionnez un rootfs.sfs"); return
        if not kernel: self._log("⚠️  Sélectionnez un kernel");     return
        if not initrd:
            kver = re.sub(r'^vmlinuz-', '', kernel.name)
            candidates = list((BOOT/"images"/"initramfs").glob(f"initramfs-{kver}*.img"))
            initrd = candidates[0] if candidates else None
        if not cmdline:
            cmdline = f"quiet zbm_system={current_system() or available_systems()[0]}"
        self._run_gen_worker(
            self._hsmgr.swap_rootfs(sfs, kexec_now=True, kernel=kernel, initrd=initrd, cmdline=cmdline),
            reload=False
        )

    @work(thread=True)
    def _run_gen_worker(self, gen: "Generator[str, None, tuple[bool, str]]", reload: bool = False) -> None:
        log_w = self.query_one("#hs-log", Log)
        self.app.call_from_thread(log_w.clear)
        def w(line: str) -> None:
            self.app.call_from_thread(log_w.write_line, line)
        result = None
        try:
            while True: w(next(gen))
        except StopIteration as e: result = e.value
        if result:
            ok2, detail = result
            w(f"\n{'✅' if ok2 else '❌'}  {detail}")
            if ok2:
                self.app.call_from_thread(self._update_current)
        if reload:
            self.app.call_from_thread(self._reload_lists)


# =============================================================================
# COHERENCE MANAGER
# =============================================================================

@dataclass
class CoherenceIssue:
    """Une divergence détectée."""
    preset:   str
    field:    str
    dataset:  str
    kind:     str   # wrong_mp|missing_ds|missing_file|bad_name|bad_cmdline|
                    # broken_symlink|incomplete_set|conflict|warn_compress|warn_atime
    actual:   str = ""
    expected: str = ""
    fixable:  bool = True

    def summary(self) -> str:
        ico = {"wrong_mp":"❌","missing_ds":"❌","missing_file":"❌",
               "bad_name":"❌","bad_cmdline":"❌","broken_symlink":"❌",
               "incomplete_set":"⚠️","conflict":"⚠️",
               "warn_compress":"⚠️","warn_atime":"⚠️"}.get(self.kind,"⚠️")
        if self.kind == "wrong_mp":
            return f"{ico} [{self.preset}] {self.dataset}  mp={self.actual!r} → {self.expected!r}"
        if self.kind == "missing_ds":
            return f"{ico} [{self.preset}] {self.field} : dataset absent  {self.dataset}"
        if self.kind == "missing_file":
            return f"{ico} [{self.preset}] {self.field} : introuvable → {self.actual}"
        if self.kind == "bad_name":
            return f"{ico} [{self.preset}] {self.field} : nommage non conforme → {self.actual}"
        if self.kind == "bad_cmdline":
            return f"{ico} [{self.preset}] cmdline/{self.field} : {self.actual!r} ≠ {self.expected!r}"
        if self.kind == "broken_symlink":
            return f"{ico} Symlink cassé : {self.dataset} → {self.actual}"
        if self.kind == "incomplete_set":
            return f"{ico} Ensemble incomplet : {self.dataset}"
        if self.kind == "conflict":
            return f"{ico} CONFLIT : {self.dataset} partagé entre {self.actual}"
        if self.kind == "warn_compress":
            return f"{ico} [{self.preset}] {self.dataset} : compression={self.actual}"
        if self.kind == "warn_atime":
            return f"{ico} [{self.preset}] {self.dataset} : atime=on"
        return f"{ico} [{self.preset}] {self.kind} {self.dataset}"


class CoherenceManager:
    """
    Vérifie TROIS couches de cohérence :
      A. Nommage des fichiers images  (via NamingHelper)
      B. Presets JSON ↔ fichiers images (existence + convention + cmdline)
      C. Datasets ZFS ↔ architecture canonique
    """

    CANONICAL: dict[str, str] = {
        # Préfixes — matcher avec startswith()
        # overlay-<s> : upper OverlayFS par système (mountpoint=none)
        "fast_pool/overlay-": "none",
        # fast_pool/var-* / log-* / tmp-* : supprimés (architecture overlay)
        "data_pool/home":     "/home",
        "data_pool/archives": "none",
        "boot_pool":          "legacy",  # invariant #47 : ZBM monte lui-même
    }

    def __init__(self, preset_mgr: PresetManager, altroot: str = "/") -> None:
        self._pm      = preset_mgr
        self._altroot = altroot.rstrip("/") if altroot != "/" else "/"

    def _canon_mp(self, ds: str) -> str:
        for prefix, mp in self.CANONICAL.items():
            if ds == prefix or ds.startswith(prefix + "/") or \
               (prefix.endswith("-") and ds.startswith(prefix)):
                return mp
        return ""

    def _eff_mp(self, mp: str) -> str:
        if mp in ("none","legacy","") or self._altroot == "/": return mp
        return f"{self._altroot}{mp}"

    def _zfs_get(self, ds: str, prop: str) -> str:
        ok2, val = run(["zfs","get","-H","-o","value",prop,ds])
        return val.strip() if ok2 else ""

    # ── A. Nommage ─────────────────────────────────────────────────────────

    def _check_naming(self) -> list[CoherenceIssue]:
        """Vérifie la cohérence des images dans /boot/images/.
        
        ARCHITECTURE :
          - kernel/initramfs/modules INDÉPENDANTS des rootfs
          - Un preset minimal requiert seulement kernel + initramfs
          - modules et rootfs sont OPTIONNELS
          - Le rootfs NE CONTIENT NI kernel NI modules
        """
        issues: list[CoherenceIssue] = []

        # Vérifier les ensembles kernel+initramfs (combinaisons de boot)
        combos = NamingHelper.list_boot_combos()
        for combo in combos:
            if combo["initramfs_label"] is None:
                # Kernel sans initramfs à la même date
                issues.append(CoherenceIssue(
                    preset="global", field="images",
                    dataset=f"kernel-{combo['kernel_label']}-{combo['date']}",
                    kind="incomplete_set",
                    actual=f"Kernel sans initramfs (date={combo['date']})",
                    fixable=False,
                ))

        # Vérifier la cohérence kernel_ver entre kernel.meta et modules.meta
        kdir = BOOT / "images" / "kernels"
        mdir = BOOT / "images" / "modules"
        if kdir.exists() and mdir.exists():
            for kf in kdir.glob("kernel-*"):
                if kf.name.endswith(".meta") or not kf.is_file():
                    continue
                k_img = NamingHelper.parse(kf)
                if not k_img or k_img.system == "failsafe":
                    continue
                k_kver = NamingHelper.read_meta(kf).get("kernel_ver","")
                # Chercher modules avec même label et même date
                mf = mdir / NamingHelper.stem("modules", "", k_img.label, k_img.date)
                if mf.exists():
                    m_kver = NamingHelper.read_meta(mf).get("kernel_ver","")
                    if k_kver and m_kver and k_kver != m_kver:
                        issues.append(CoherenceIssue(
                            preset="global", field="meta",
                            dataset=f"{k_img.label}/{k_img.date}",
                            kind="warn_meta_kver",
                            actual=f"kernel_ver divergents: kernel={k_kver} modules={m_kver}",
                            fixable=False,
                        ))

        # Fichiers avec nommage non conforme
        for d in (BOOT / "images"/"kernels", BOOT / "images"/"initramfs",
                  BOOT / "images"/"modules",  BOOT / "images"/"rootfs",
                  BOOT / "images"/"startup",  BOOT / "images"/"failsafe"):
            if not d.exists(): continue
            for f in sorted(d.iterdir()):
                if not f.is_file(): continue
                if f.suffix == ".meta": continue
                if NamingHelper.parse(f) is None:
                    issues.append(CoherenceIssue(
                        preset="global", field="images", dataset=str(f),
                        kind="bad_name", actual=f.name, fixable=False,
                    ))
                elif not NamingHelper.meta_path(f).exists():
                    issues.append(CoherenceIssue(
                        preset="global", field="meta", dataset=str(f),
                        kind="warn_no_meta", actual=f.name, fixable=True,
                    ))

        # Python SFS
        py_dir = BOOT / "images" / "startup"
        if py_dir.exists():
            py_sfs = sorted(f for f in py_dir.iterdir()
                           if f.is_file() and f.name.startswith("python-") and f.suffix == ".sfs")
            if not py_sfs:
                issues.append(CoherenceIssue(
                    preset="global", field="python_sfs", dataset="startup",
                    kind="incomplete_set", actual="Aucun python-*.sfs", fixable=False,
                ))
        return issues

    # ── B. Presets ↔ Images ─────────────────────────────────────────────────

    def _check_preset_images(self, preset: dict) -> list[CoherenceIssue]:
        """Vérifie que les fichiers d'un preset existent.
        
        rootfs=null est VALIDE pour les presets initiaux et minimaux.
        kernel/initramfs/modules : jamais de system dans le nom.
        """
        issues: list[CoherenceIssue] = []
        name = preset.get("name","?")
        ptype = preset.get("type","")
        image_set = preset.get("_image_set","")

        for fkey in ("kernel","initramfs","modules","rootfs"):
            fpath = preset.get(fkey,"") or ""
            # rootfs=null valide pour initial/minimal
            if not fpath or fpath == "null":
                if fkey == "rootfs" and ptype in ("initial","minimal"):
                    continue
                if fkey in ("modules",):
                    continue  # toujours optionnel
                if not fpath: continue
                continue
            p = Path(fpath)
            if not p.exists():
                issues.append(CoherenceIssue(
                    preset=name, field=fkey, dataset=fpath,
                    kind="missing_file", actual=fpath, fixable=False,
                ))
                continue
            img = NamingHelper.parse(p)
            if img is None:
                issues.append(CoherenceIssue(
                    preset=name, field=fkey, dataset=fpath,
                    kind="bad_name", actual=p.name, fixable=False,
                ))
                continue
            # Cohérence d'ensemble
            if image_set and img.set_key != image_set:
                issues.append(CoherenceIssue(
                    preset=name, field=fkey, dataset=fpath,
                    kind="bad_cmdline",
                    actual=img.set_key, expected=image_set, fixable=False,
                ))

        # Cmdline
        cmdline = preset.get("cmdline","")
        if cmdline:
            checks = [
                ("zbm_system",  name),
                # zbm_var / zbm_log supprimés (architecture overlay)
                ("zbm_overlay", preset.get("overlay_dataset","")),
                ("zbm_rootfs",  preset.get("rootfs","")),
                ("zbm_modules", preset.get("modules","")),
            ]
            for param, expected_val in checks:
                if not expected_val: continue
                m = re.search(rf'{param}=(\S+)', cmdline)
                actual_val = m.group(1) if m else ""
                if actual_val and actual_val != expected_val:
                    issues.append(CoherenceIssue(
                        preset=name, field=param, dataset=param,
                        kind="bad_cmdline", actual=actual_val,
                        expected=expected_val, fixable=True,
                    ))
        return issues

    # ── C. Datasets ZFS ─────────────────────────────────────────────────────

    def _check_ds(self, ds: str, preset: str, field: str) -> list[CoherenceIssue]:
        issues: list[CoherenceIssue] = []
        expected_mp = self._canon_mp(ds)
        if not dataset_exists(ds):
            issues.append(CoherenceIssue(
                preset=preset, field=field, dataset=ds,
                kind="missing_ds", expected=expected_mp, fixable=False,
            ))
            return issues
        actual_mp = self._zfs_get(ds,"mountpoint")
        eff = self._eff_mp(expected_mp)
        if expected_mp and actual_mp not in (expected_mp, eff):
            issues.append(CoherenceIssue(
                preset=preset, field=field, dataset=ds,
                kind="wrong_mp", actual=actual_mp, expected=expected_mp, fixable=True,
            ))
        comp = self._zfs_get(ds,"compression")
        if comp in ("off","lzjb","gzip"):
            issues.append(CoherenceIssue(
                preset=preset, field=field, dataset=ds,
                kind="warn_compress", actual=comp, expected="zstd", fixable=True,
            ))
        atime = self._zfs_get(ds,"atime")
        if atime == "on":
            issues.append(CoherenceIssue(
                preset=preset, field=field, dataset=ds,
                kind="warn_atime", actual="on", expected="off", fixable=True,
            ))
        return issues

    def _check_symlinks(self) -> list[CoherenceIssue]:
        """Vérifie les symlinks dans $BOOT/boot/ (= répertoire ZBM)."""
        issues: list[CoherenceIssue] = []
        links_dir = BOOT / "boot"

        for link_name in ("vmlinuz","initrd.img","modules.sfs","rootfs.sfs"):
            lp = links_dir / link_name
            # modules.sfs et rootfs.sfs sont optionnels
            optional = link_name in ("modules.sfs", "rootfs.sfs")
            if not lp.is_symlink():
                if not optional:
                    issues.append(CoherenceIssue(
                        preset="global", field="symlink", dataset=link_name,
                        kind="broken_symlink", actual="(absent)", fixable=False,
                    ))
                continue
            target = readlink(lp)
            if not lp.is_file():
                issues.append(CoherenceIssue(
                    preset="global", field="symlink", dataset=link_name,
                    kind="broken_symlink", actual=target, fixable=False,
                ))
                continue
            # Nommage de la cible
            img = NamingHelper.parse(Path(target))
            if img is None:
                issues.append(CoherenceIssue(
                    preset="global", field="symlink", dataset=link_name,
                    kind="bad_name", actual=target, fixable=False,
                ))

        # Failsafe symlinks (aussi dans $BOOT/boot/)
        for link_name in FAILSAFE_SYMLINKS:
            lp = links_dir / link_name
            if not lp.is_symlink(): continue
            if not lp.is_file():
                issues.append(CoherenceIssue(
                    preset="global", field="failsafe", dataset=link_name,
                    kind="broken_symlink", actual=readlink(lp), fixable=False,
                ))
        return issues

    def _check_conflicts(self, presets: list[dict]) -> list[CoherenceIssue]:
        issues: list[CoherenceIssue] = []
        owners: dict[str, list[str]] = {}
        for p in presets:
            name = p.get("name","?")
            # var/log/tmp_dataset supprimés — plus de conflit possible
            for f in ("overlay_dataset",):  # seul l'overlay peut être en conflit
                ds = p.get(f,"")
                if ds: owners.setdefault(ds,[]).append(name)
        for ds, names in owners.items():
            if len(names) > 1:
                issues.append(CoherenceIssue(
                    preset=names[0], field="conflict", dataset=ds,
                    kind="conflict", actual=" + ".join(names), fixable=False,
                ))
        return issues

    # ── Vérification complète ────────────────────────────────────────────────

    def check_all(
        self, filter_preset: str = ""
    ) -> Generator[str, None, list[CoherenceIssue]]:
        all_issues: list[CoherenceIssue] = []
        presets = self._pm.load()
        if filter_preset:
            presets = [p for p in presets if p.get("name") == filter_preset]

        # A. Nommage
        yield "━━ A. Nommage des images ━━"
        issues_naming = self._check_naming()
        for i in issues_naming:
            yield f"  {i.summary()}"
            all_issues.append(i)
        if not issues_naming:
            sets = NamingHelper.list_sets()
            for key, imgs in sets.items():
                yield f"  ✅ {key}  [{len(imgs)} fichiers]"

        # B. Presets ↔ Images
        yield ""
        yield "━━ B. Presets JSON ↔ Images ━━"
        for preset in presets:
            name = preset.get("name","?")
            prot = "🔒 " if preset.get("protected") else ""
            yield f"  {prot}[{name}]  _image_set={preset.get('_image_set','—')}"
            pissues = self._check_preset_images(preset)
            for i in pissues:
                yield f"    {i.summary()}"
                all_issues.append(i)
            if not pissues:
                yield f"    ✅ Fichiers et cmdline cohérents"

        # C. ZFS
        yield ""
        yield "━━ C. Datasets ZFS ━━"
        if not run(["zpool","list","boot_pool"])[0]:
            yield "  ❌ boot_pool non importé"
            all_issues.append(CoherenceIssue(
                preset="global", field="pool", dataset="boot_pool",
                kind="missing_ds", fixable=False,
            ))
        else:
            mp = self._zfs_get("boot_pool","mountpoint")
            # Invariant #47 : mountpoint=legacy (ZBM monte lui-même au boot)
            # "/boot" serait incorrect et empêcherait ZBM de trouver les kernels
            if mp == "legacy":
                yield f"  ✅ boot_pool  mp=legacy"
            elif mp == "/boot":
                yield f"  ❌ boot_pool  mp={mp!r} — doit être legacy (ZBM monte le pool, pas le système)"
                all_issues.append(CoherenceIssue(
                    preset="global", field="pool", dataset="boot_pool",
                    kind="wrong_mp", actual=mp, expected="legacy", fixable=True,
                ))
            else:
                yield f"  ❌ boot_pool  mp={mp!r} attendu legacy"
                all_issues.append(CoherenceIssue(
                    preset="global", field="pool", dataset="boot_pool",
                    kind="wrong_mp", actual=mp, expected="legacy", fixable=True,
                ))
        for preset in presets:
            name = preset.get("name","?")
            for field in ("overlay_dataset", "home_dataset"):  # var/log/tmp supprimés
                ds = preset.get(field,"")
                if not ds: continue
                for i in self._check_ds(ds, name, field):
                    yield f"  {i.summary()}"
                    all_issues.append(i)

        # D. Symlinks
        yield ""
        yield "━━ D. Symlinks $BOOT/boot/ ━━"
        slink_issues = self._check_symlinks()
        for i in slink_issues:
            yield f"  {i.summary()}"
            all_issues.append(i)
        if not slink_issues:
            yield "  ✅ Symlinks actifs et failsafe OK"

        # E. Conflits
        yield ""
        yield "━━ E. Conflits inter-presets ━━"
        cissues = self._check_conflicts(presets)
        for i in cissues:
            yield f"  {i.summary()}"
            all_issues.append(i)
        if not cissues:
            yield "  ✅ Aucun conflit"

        yield ""
        errors   = sum(1 for i in all_issues if i.kind not in ("warn_compress","warn_atime","conflict","incomplete_set"))
        warnings = len(all_issues) - errors
        yield f"━━ {errors} erreur(s)  {warnings} avertissement(s) ━━"
        return all_issues

    # ── Correction ──────────────────────────────────────────────────────────

    def fix(self, issues: list[CoherenceIssue]
            ) -> Generator[str, None, tuple[int, int]]:
        fixed = skipped = 0
        for issue in issues:
            if not issue.fixable:
                yield f"  ⏭  {issue.summary()}"
                skipped += 1
                continue
            if issue.kind == "wrong_mp":
                ok2, msg = run(["zfs","set",f"mountpoint={issue.expected}",issue.dataset])
                if ok2: yield f"  🔧 {issue.dataset}  mp→{issue.expected}"; fixed += 1
                else:   yield f"  ❌ {msg}"; skipped += 1
            elif issue.kind == "warn_compress":
                ok2, _ = run(["zfs","set","compression=zstd",issue.dataset])
                if ok2: yield f"  🔧 {issue.dataset} compression→zstd"; fixed += 1
                else:   skipped += 1
            elif issue.kind == "warn_atime":
                ok2, _ = run(["zfs","set","atime=off",issue.dataset])
                if ok2: yield f"  🔧 {issue.dataset} atime→off"; fixed += 1
                else:   skipped += 1
            elif issue.kind == "bad_cmdline":
                presets2 = self._pm.load()
                for p in presets2:
                    if p.get("name") != issue.preset: continue
                    old_cmd = p.get("cmdline","")
                    new_cmd = re.sub(rf'{issue.field}=\S+',
                                     f'{issue.field}={issue.expected}', old_cmd)
                    if new_cmd == old_cmd and issue.expected:
                        new_cmd += f" {issue.field}={issue.expected}"
                    p["cmdline"] = new_cmd
                    if self._pm.save(p):
                        yield f"  🔧 cmdline [{issue.preset}] {issue.field}→{issue.expected}"; fixed += 1
                    else:
                        yield f"  ❌ Sauvegarde échouée"; skipped += 1
                    break
            elif issue.kind == "warn_no_meta":
                img_path = Path(issue.dataset)
                if img_path.exists():
                    meta_p = NamingHelper.meta_path(img_path)
                    try:
                        img_info = NamingHelper.parse(img_path)
                        meta_data = {
                            "type": img_info.type_ if img_info else "",
                            "system": img_info.system if img_info else "",
                            "label": img_info.label if img_info else "",
                            "date": img_info.date if img_info else "",
                            "built": datetime.now().isoformat(),
                            "size_bytes": img_path.stat().st_size,
                            "builder": "coherence-fix",
                        }
                        meta_p.write_text(json.dumps(meta_data, indent=2) + "\n")
                        yield f"  🔧 Meta créé : {meta_p.name}"; fixed += 1
                    except Exception as e:
                        yield f"  ❌ Meta : {e}"; skipped += 1
                else:
                    skipped += 1
            else:
                yield f"  ⏭  correction manuelle : {issue.summary()}"; skipped += 1
        yield f"\n  🔧 {fixed} correction(s)  ⏭  {skipped} ignoré(s)"
        return fixed, skipped


# =============================================================================
# ÉCRAN : COHÉRENCE
# =============================================================================

class CoherenceScreen(Screen):
    BINDINGS = [Binding("escape","app.pop_screen","Retour")]

    def __init__(self, preset_mgr: PresetManager) -> None:
        super().__init__()
        self._pm     = preset_mgr
        self._issues: list[CoherenceIssue] = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("🔧  COHÉRENCE  (datasets / mountpoints / cmdline)", classes="screen-title")

        with Horizontal(id="coh-top"):
            yield Select(
                options=[("Tous les presets","__all__")] + [
                    (p.get("label", p.get("name","?")), p.get("name","?"))
                    for p in self._pm.load()
                ],
                value="__all__",
                id="coh-filter",
            )
            yield Input("/", id="coh-altroot", placeholder="altroot (/ ou /mnt/zbm)")
            yield Button("🔍 Vérifier",  variant="primary",  id="btn-check")
            yield Button("🔧 Corriger",  variant="warning",  id="btn-fix")
            yield Button("🔙 Retour",    variant="default",  id="btn-back")

        yield Log(id="coh-log", auto_scroll=True)

        # Table des problèmes
        yield Static("Problèmes détectés", classes="panel-title")
        yield DataTable(id="coh-table", cursor_type="row")
        yield Footer()

    def on_mount(self) -> None:
        t = self.query_one("#coh-table", DataTable)
        t.add_columns("Preset","Champ","Dataset","Problème","Réel","Attendu","Corr.")

    def _get_filter(self) -> str:
        v = getattr(self.query_one("#coh-filter", Select), "value", "__all__")
        return "" if v == "__all__" else (v or "")

    def _get_altroot(self) -> str:
        return self.query_one("#coh-altroot", Input).value.strip() or "/"

    def _get_mgr(self) -> CoherenceManager:
        return CoherenceManager(self._pm, altroot=self._get_altroot())

    def _populate_table(self, issues: list[CoherenceIssue]) -> None:
        t = self.query_one("#coh-table", DataTable)
        t.clear()
        for i in issues:
            t.add_row(
                i.preset, i.field, i.dataset,
                i.kind,
                i.actual[:30] if i.actual else "—",
                i.expected[:30] if i.expected else "—",
                "✅" if i.fixable else "—",
                key=f"{i.preset}:{i.dataset}:{i.kind}",
            )

    @on(Button.Pressed,"#btn-back")
    def go_back(self) -> None: self.app.pop_screen()

    @on(Button.Pressed,"#btn-check")
    def do_check(self) -> None:
        self._run_check_worker()

    @work(thread=True)
    def _run_check_worker(self) -> None:
        mgr  = self._get_mgr()
        filt = self._get_filter()
        log_w = self.query_one("#coh-log", Log)
        self.app.call_from_thread(log_w.clear)
        def w(line: str) -> None:
            self.app.call_from_thread(log_w.write_line, line)
        issues: list[CoherenceIssue] = []
        try:
            gen = mgr.check_all(filter_preset=filt)
            while True: w(next(gen))
        except StopIteration as e:
            issues = e.value or []
        self._issues = issues
        self.app.call_from_thread(self._populate_table, issues)

    @on(Button.Pressed,"#btn-fix")
    def do_fix(self) -> None:
        if not self._issues:
            self.notify("Lancez d'abord une vérification", severity="warning")
            return
        fixable = [i for i in self._issues if i.fixable]
        if not fixable:
            self.notify("Aucun problème corrigeable automatiquement", severity="warning")
            return
        mgr = self._get_mgr()
        self._run_fix(mgr, fixable)

    @work(thread=True)
    def _run_fix(self, mgr: "CoherenceChecker", fixable: list) -> None:
        log_w = self.query_one("#coh-log", Log)
        def w(line: str) -> None:
            self.app.call_from_thread(log_w.write_line, line)
        result = None
        try:
            gen = mgr.fix(fixable)
            while True: w(next(gen))
        except StopIteration as e: result = e.value
        if result:
            fixed, skipped = result
            self.app.call_from_thread(
                lambda: self.notify(f"🔧 {fixed} correction(s), {skipped} ignoré(s)")
            )
        self.app.call_from_thread(self.do_check)


# =============================================================================
# ÉCRAN : FAILSAFE (lecture seule)
# =============================================================================

class FailsafeScreen(Screen):
    BINDINGS = [Binding("escape","app.pop_screen","Retour")]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("⛑  FAILSAFE — lecture seule", classes="screen-title")
        yield ScrollableContainer(Static(id="content"))
        yield Button("🔙 Retour",variant="default",id="btn-back")
        yield Footer()

    def on_mount(self) -> None:
        lines: list[str] = []
        meta = NamingHelper.failsafe_meta()
        if meta:
            lines += [f"[bold]{meta.get('_meta_file','failsafe.meta')}[/bold]",""]
            LABEL_MAP = {
                "type": "type", "system": "système", "label": "label",
                "date": "date YYYYMMDD", "built": "construit le",
                "kernel_ver": "version kernel", "size_bytes": "taille",
                "sha256": "sha256", "builder": "builder",
            }
            for k in ("type","system","label","date","built","kernel_ver",
                      "size_bytes","sha256","builder"):
                v = meta.get(k)
                if v is None: continue
                if k == "size_bytes" and isinstance(v, (int, float)) and v > 0:
                    v = human_size(v)
                lines.append(f"  [bold]{LABEL_MAP.get(k,k):<22}[/bold] {v}")
        else:
            lines += ["[yellow]Aucun failsafe créé[/yellow]","",
                      "Créez-le manuellement :",
                      "  bash create-failsafe.sh <s> <label>",
                      "  bash update-failsafe-links.sh"]
        lines += ["","─── Symlinks $BOOT ─────────────────────"]
        for link in FAILSAFE_SYMLINKS:
            lp = BOOT / "boot" / link
            target = readlink(lp)
            img = NamingHelper.parse(Path(target)) if target != "—" else None
            name_ok = "✅" if (lp.is_file() and img is not None) else ("⚠️" if lp.is_file() else "❌")
            lines.append(f"  {name_ok}  {link:<32} → {target}")
            if img:
                lines.append(f"       [dim]set: {img.set_key}[/dim]")
        lines += ["","─── Ensembles failsafe disponibles ─────"]
        for f in sorted(FAILSAFE_DIR.glob("kernel-failsafe-*")) if FAILSAFE_DIR.exists() else []:
            img = NamingHelper.parse(f)
            if img:
                complete = NamingHelper.set_complete("failsafe", img.label, img.date)
                lines.append(f"  {'✅' if complete else '⚠️'}  failsafe/{img.label}/{img.date}")
        lines += ["","[dim]Géré par 06/update-failsafe-links.sh uniquement[/dim]"]
        self.query_one("#content",Static).update("\n".join(lines))

    @on(Button.Pressed,"#btn-back")
    def go_back(self) -> None: self.app.pop_screen()


# =============================================================================
# ÉCRAN PRINCIPAL
# =============================================================================

class MainScreen(Screen):
    BINDINGS = [Binding("q","quit_app","Quitter"), Binding("r","reload","Rafraîchir")]

    def __init__(self) -> None:
        super().__init__()
        self._pm    = PresetManager()
        self._smgr  = SnapshotManager()
        self._pmgr  = ProfileManager()
        self._stmgr = StreamManager()
        self._presets: list[dict] = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="layout"):
            with Vertical(id="left"):
                yield Static("Systèmes", classes="panel-title")
                yield ListView(id="sys-list")
                yield Static(id="active-label", classes="active-info")
            with Vertical(id="right"):
                yield Static("", id="preset-detail")
                # Statut stream en haut
                with Horizontal(id="stream-bar"):
                    yield Static("📡 Stream :", id="stream-state")
                    yield Static("", id="stream-cd")
                with Horizontal(id="main-actions"):
                    yield Button("🚀 Activer",        variant="success", id="btn-activate")
                    yield Button("📡 Stream",          variant="warning", id="btn-stream")
                    yield Button("✏️  Config preset",   variant="primary", id="btn-cfg")
                    yield Button("📸 Snapshots",        variant="default", id="btn-snap")
                    yield Button("🔀 Hot-Swap",         variant="warning", id="btn-hotswap")
                    yield Button("🔧 Cohérence",        variant="primary", id="btn-coherence")
                    yield Button("⛑  Failsafe",         variant="default", id="btn-fs")
                    yield Button("⚙️  Régénérer ZBM",    variant="primary", id="btn-regen")
                    yield Button("⚙  Kernels",            variant="warning", id="btn-kernels",
                                 tooltip="Lister, sélectionner, installer les kernels dans boot_pool")
                    yield Button("🚀 Déploiement",         variant="success", id="btn-deploy",
                                 tooltip="Tableau de bord complet du déploiement")
                yield Static("", id="status-bar")
                yield Static("Symlinks $BOOT/boot/", classes="panel-title")
                yield DataTable(id="link-table", cursor_type="none")
        yield Footer()

    def on_mount(self) -> None:
        t = self.query_one("#link-table",DataTable)
        t.add_columns("Lien","Cible","Ensemble","État","Type")
        self._reload()
        self.set_interval(3.0, self._refresh_stream_status)

    def _reload(self) -> None:
        lv = self.query_one("#sys-list",ListView); lv.clear()
        self._presets = self._pm.load()
        active = self._pm.active_name()
        running = current_system()
        for p in self._presets:
            name=p.get("name","?"); label=p.get("label",name)
            marks=[]
            if name==active:   marks.append("⚡")
            if name==running:  marks.append("▶")
            if p.get("protected"): marks.append("🔒")
            ptype = p.get("type","")
            itype = p.get("init_type","")
            if ptype=="prepared":   marks.append("[cyan]préparé[/cyan]")
            elif ptype=="normal":   marks.append("[dim]normal[/dim]")
            elif ptype=="stream":   marks.append("[magenta]stream[/magenta]")
            elif ptype=="minimal":  marks.append("[dim]minimal[/dim]")
            elif ptype in ("initial",""): marks.append("[yellow]initial[/yellow]")
            # Rootfs absent → boot initial
            if not p.get("rootfs") or p.get("rootfs") == "null":
                marks.append("[yellow]sans rootfs[/yellow]")
            suffix = " "+" ".join(marks) if marks else ""
            lv.append(ListItem(Label(f"{label}{suffix}"), name=name))

        t = self.query_one("#link-table",DataTable); t.clear()
        for s in self._pm.symlink_status():
            t.add_row(s["name"],s["target"],s.get("set_key","—"),
                      "✅" if s["ok"] else "❌",
                      "failsafe" if s["failsafe"] else "actif")
        self.query_one("#active-label",Static).update(
            f"Actif : [bold]{active or '—'}[/bold]")
        self._refresh_stream_status()

    def _refresh_stream_status(self) -> None:
        state = self._stmgr.state()
        cd    = self._stmgr.countdown()
        colors = {"running":"green","pending":"yellow","stopped":"red",
                  "cancelled":"dim","unknown":"dim"}
        col = colors.get(state,"dim")
        self.query_one("#stream-state",Static).update(
            f"📡 Stream : [{col}]{state}[/{col}]")
        self.query_one("#stream-cd",Static).update(
            f"[yellow]  démarrage dans {cd}s[/yellow]" if cd>0 else "")

    def _sel(self) -> dict | None:
        lv = self.query_one("#sys-list",ListView)
        idx = lv.index
        if idx is None or idx>=len(self._presets): return None
        return self._presets[idx]

    def _status(self, msg: str) -> None:
        self.query_one("#status-bar",Static).update(msg)

    @on(ListView.Selected,"#sys-list")
    def on_sel(self,_: ListView.Selected) -> None:
        """Affiche les détails d'un preset sélectionné.
        Montre exactement ce qui sera booté : kernel / initramfs / modules / rootfs.
        """
        p = self._sel()
        if not p: return
        name = p.get("name","?")
        ptype = p.get("type","?")
        init_type = p.get("init_type","?")

        # Kernel
        kernel_path = p.get("kernel","") or ""
        k_name = Path(kernel_path).name if kernel_path else "—"
        k_img  = NamingHelper.parse(Path(kernel_path)) if kernel_path else None
        k_meta = NamingHelper.read_meta(Path(kernel_path)) if kernel_path and Path(kernel_path).exists() else {}
        kver   = k_meta.get("kernel_ver","") or p.get("_kernel_ver","")
        k_exists = bool(kernel_path and Path(kernel_path).exists())

        # Initramfs
        init_path = p.get("initramfs","") or ""
        i_name = Path(init_path).name if init_path else "—"
        i_meta = NamingHelper.read_meta(Path(init_path)) if init_path and Path(init_path).exists() else {}
        i_type = i_meta.get("init_type","") or init_type
        i_exists = bool(init_path and Path(init_path).exists())

        # Modules
        mod_path = p.get("modules","") or ""
        m_name = Path(mod_path).name if mod_path else "— (aucun)"
        m_exists = bool(mod_path and mod_path != "null" and Path(mod_path).exists())

        # Rootfs
        rootfs_path = p.get("rootfs","") or ""
        r_name = Path(rootfs_path).name if rootfs_path and rootfs_path != "null" else "— (boot initial / sans rootfs)"
        r_img = NamingHelper.parse(Path(rootfs_path)) if rootfs_path and rootfs_path != "null" else None
        r_exists = bool(rootfs_path and rootfs_path != "null" and Path(rootfs_path).exists())

        image_set = p.get("_image_set","")
        if k_img and not image_set:
            image_set = f"{k_img.label}/{k_img.date}"
        if r_img:
            image_set += f" + rootfs:{r_img.system}/{r_img.label}"

        lines = [
            f"[bold]{p.get('label', name)}[/bold]",
            "",
            f"  🏷  type      : {ptype}",
            f"  🔧 init      : {i_type or '?'}",
            f"  📦 ensemble  : {image_set or p.get('_image_set','—')}",
            "",
            f"  ⚙️  kernel    : {k_name}" + (f"  [green]✓[/green]" if k_exists else "  [red]✗ MANQUANT[/red]"),
            f"       kver    : {kver or '?'}",
            f"  🔧 initramfs : {i_name}" + (f"  [green]✓[/green]" if i_exists else "  [red]✗ MANQUANT[/red]"),
            f"       type    : {i_type or '?'}",
            f"  📦 modules   : {m_name}" + (f"  [green]✓[/green]" if m_exists else ("" if not mod_path or mod_path=="null" else "  [red]✗ MANQUANT[/red]")),
            f"  💿 rootfs    : {r_name}" + (f"  [green]✓[/green]" if r_exists else ("" if not rootfs_path or rootfs_path=="null" else "  [red]✗ MANQUANT[/red]")),
            "",
            f"  📁 overlay   : {p.get('overlay_dataset','—')}  [upper, rw — /var /tmp via lower+upper]",
            f"  📊 priorité  : {p.get('priority','?')}",
            f"  🌐 réseau    : {p.get('network_mode','?')}",
            f"  📡 stream    : {'configuré (' + ptype + ')' if p.get('stream_key') else '—'}",
        ]

        if not rootfs_path or rootfs_path == "null":
            exec_cmd_v = p.get("exec","")
            exec_display = exec_cmd_v if exec_cmd_v else "(auto : Python TUI → shell)"
            lines.append("")
            lines.append("  [yellow]🔧 Mode INIT-ONLY[/yellow]")
            lines.append(f"  [yellow]   exec   : {exec_display}[/yellow]")
            lines.append("  [yellow]   env    : initramfs pur — /mnt/boot disponible[/yellow]")
            lines.append("  [yellow]   aucun overlay, aucun pivot_root[/yellow]")

        if p.get("protected"):
            lines += ["","  [bold red]🔒 Preset protégé — non modifiable[/bold red]"]

        self.query_one("#preset-detail",Static).update("\n".join(lines))

    @on(Button.Pressed,"#btn-activate")
    def do_activate(self) -> None:
        p = self._sel()
        if not p: self._status("⚠️  Sélectionnez un système"); return
        if p.get("protected"): self._status("⛑  Failsafe non activable"); return
        ok, msg = self._pm.set_active(p)
        self._status(("✅ " if ok else "❌ ")+msg)
        if ok: self._reload()

    @on(Button.Pressed,"#btn-stream")
    def do_stream(self) -> None:
        p = self._sel()
        if not p: self._status("⚠️  Sélectionnez un système"); return
        if p.get("type")!="prepared":
            self._status("⚠️  Stream disponible uniquement sur les presets de type 'préparé'"); return
        self.app.push_screen(StreamScreen(p, self._stmgr))

    @on(Button.Pressed,"#btn-cfg")
    def do_cfg(self) -> None:
        p = self._sel()
        if p and p.get("protected"):
            self._status("⛑  Failsafe non modifiable"); return
        self.app.push_screen(
            PresetConfigScreen(self._pm, p),
            callback=lambda _: self._reload())

    @on(Button.Pressed,"#btn-snap")
    def do_snap(self) -> None:
        p = self._sel()
        if not p: self._status("⚠️  Sélectionnez un système"); return
        if p.get("protected"): self._status("⛑  Pas de snapshots pour le failsafe"); return
        self.app.push_screen(SnapshotScreen(self._smgr,self._pmgr,self._pm,p["name"]))

    @on(Button.Pressed,"#btn-coherence")
    def do_coherence(self) -> None:
        self.app.push_screen(CoherenceScreen(self._pm))

    @on(Button.Pressed,"#btn-hotswap")
    def do_hotswap(self) -> None:
        self.app.push_screen(HotSwapScreen(self._pm))

    @on(Button.Pressed,"#btn-fs")
    def do_fs(self) -> None: self.app.push_screen(FailsafeScreen())

    @on(Button.Pressed,"#btn-regen")
    def do_regen(self) -> None:
        log_w = self.query_one("#status-bar",Static)
        log_w.update("⚙️  Régénération ZFSBootMenu...")
        ok, out = run(["generate-zbm","--config","/etc/zfsbootmenu/config.yaml"],timeout=120)
        self._status(("✅ ZBM régénéré" if ok else "❌ Erreur ZBM")+f"  {out[:60]}")

    @on(Button.Pressed,"#btn-kernels")
    def do_kernels(self) -> None:
        self.app.push_screen(
            KernelSelectScreen(self._pm),
            callback=lambda _: self._reload()
        )

    @on(Button.Pressed,"#btn-deploy")
    def do_deploy(self) -> None:
        self.app.push_screen(
            DeployScreen(),
            callback=lambda _: self._reload()
        )

    def action_reload(self) -> None: self._reload(); self._status("✅ Rafraîchi")
    def action_quit_app(self) -> None: self.app.exit()


# =============================================================================
# APPLICATION
# =============================================================================

# =============================================================================
# KernelSelectScreen — Sélection d'un kernel installé dans boot_pool
# Accessible depuis MainScreen (bouton Kernels) et DeployScreen (étape 3)
# =============================================================================
class KernelSelectScreen(Screen):
    """Liste les kernels installés dans boot_pool.
    Permet de sélectionner un kernel actif, de voir ses métadonnées,
    d'en supprimer un ou de lancer l'installation d'un nouveau.
    """
    BINDINGS = [Binding("escape", "app.pop_screen", "Retour")]

    def __init__(self, preset_mgr: PresetManager | None = None) -> None:
        super().__init__()
        self._pm = preset_mgr
        self._scanner = KernelScanner()
        self._kernels: list[KernelEntry] = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("⚙  KERNELS INSTALLÉS  —  boot_pool/images/kernels/", classes="screen-title")
        with Horizontal(id="ks-layout"):
            with Vertical(id="ks-left"):
                yield Static("Kernels détectés", classes="panel-title")
                yield ListView(id="ks-kernel-list")
                with Horizontal(id="ks-btns"):
                    yield Button("✅ Activer symlink", variant="success",  id="btn-ks-activate",
                                 tooltip="Met à jour vmlinuz + initrd.img vers ce kernel")
                    yield Button("🗑 Supprimer",       variant="error",    id="btn-ks-delete",
                                 tooltip="Supprime kernel + modules.sfs du boot_pool")
                    yield Button("🔄 Actualiser",      variant="default",  id="btn-ks-refresh")
            with Vertical(id="ks-right"):
                yield Static("Détail", classes="panel-title")
                yield Static(id="ks-detail", classes="ks-detail")
                yield Static("Actions rapides", classes="panel-title")
                with Horizontal():
                    yield Button("📥 Installer depuis le live", variant="primary", id="btn-ks-install",
                                 tooltip="Copie kernel+modules depuis le système live")
                    yield Button("🔙 Retour", variant="default", id="btn-ks-back")
                yield Static("Log", classes="panel-title")
                yield Log(id="ks-log", auto_scroll=True)
        yield Footer()

    def on_mount(self) -> None:
        self._do_reload()

    def _reload(self) -> None:
        self._do_reload()

    @work(thread=True)
    def _do_reload(self) -> None:
        kernels = self._scanner.scan()
        def update() -> None:
            self._kernels = kernels
            lv = self.query_one("#ks-kernel-list", ListView)
            lv.clear()
            if not kernels:
                lv.append(ListItem(Label("  (aucun kernel installé)"), name=""))
            for k in kernels:
                active_mark = " [bold green]◀ actif[/bold green]" if k.is_active else ""
                mod_mark    = " [cyan]+mod[/cyan]" if k.has_modules else ""
                age = f"  [dim]{k.age_days}j[/dim]" if k.age_days >= 0 else ""
                lv.append(ListItem(
                    Label(f"kernel-{k.label}-{k.date}{active_mark}{mod_mark}{age}"),
                    name=str(k.path)
                ))
            self._update_detail(None)
            self._update_btn_states()
        self.app.call_from_thread(update)

    def _sel_kernel(self) -> KernelEntry | None:
        lv = self.query_one("#ks-kernel-list", ListView)
        if lv.index is None or lv.index >= len(self._kernels):
            return None
        return self._kernels[lv.index]

    def _update_btn_states(self) -> None:
        has = bool(self._kernels)
        for btn_id in ("#btn-ks-activate", "#btn-ks-delete"):
            try:
                self.query_one(btn_id, Button).disabled = not has
            except Exception:
                pass

    def _update_detail(self, k: KernelEntry | None) -> None:
        if k is None:
            self.query_one("#ks-detail", Static).update(
                "Sélectionnez un kernel dans la liste."
            )
            return
        lines = [
            f"[bold]kernel-{k.label}-{k.date}[/bold]",
            "",
            f"  Fichier   : {k.filename}",
            f"  Taille    : {k.size_human}",
            f"  kver      : {k.kver or '(inconnu)'}",
            f"  Date      : {k.date_display}  ({k.age_days}j)",
            f"  Actif     : {'[green]Oui[/green]' if k.is_active else 'Non'}",
            "",
            f"  Modules   : {'[cyan]' + k.modules_size_human + '[/cyan]' if k.has_modules else '[dim]absent[/dim]'}",
        ]
        if k.modules_path:
            lines.append(f"  Mod.path  : {k.modules_path.name}")
        if k.meta:
            built = k.meta.get("built", "")
            sha   = k.meta.get("sha256", "")[:16]
            bldr  = k.meta.get("builder", "")
            if built:
                lines.append(f"  Construit : {built[:19]}")
            if sha:
                lines.append(f"  SHA256    : {sha}…")
            if bldr:
                lines.append(f"  Builder   : {bldr}")
        self.query_one("#ks-detail", Static).update("\n".join(lines))

    @on(ListView.Highlighted, "#ks-kernel-list")
    def on_highlight(self, _: ListView.Highlighted) -> None:
        k = self._sel_kernel()
        self._update_detail(k)
        for btn_id in ("#btn-ks-activate", "#btn-ks-delete"):
            try:
                self.query_one(btn_id, Button).disabled = (k is None)
            except Exception:
                pass

    @on(Button.Pressed, "#btn-ks-back")
    def go_back(self) -> None:
        self.app.pop_screen()

    @on(Button.Pressed, "#btn-ks-refresh")
    def do_refresh(self) -> None:
        self._scanner = KernelScanner()
        self._reload()
        self.query_one("#ks-log", Log).write_line("✅ Actualisé")

    @on(Button.Pressed, "#btn-ks-activate")
    def do_activate(self) -> None:
        k = self._sel_kernel()
        if not k:
            self.query_one("#ks-log", Log).write_line("⚠  Sélectionnez un kernel")
            return
        log = self.query_one("#ks-log", Log)
        log.write_line(f"🔗 Activation symlink → kernel-{k.label}-{k.date}")
        # Mettre à jour vmlinuz
        vmlinuz = self._scanner.boot / "vmlinuz"
        rel_k = Path("images") / "kernels" / k.filename
        try:
            vmlinuz.unlink(missing_ok=True)
            vmlinuz.symlink_to(str(rel_k))
            log.write_line(f"  ✅ vmlinuz → {k.filename}")
        except Exception as exc:
            log.write_line(f"  ❌ {exc}")
            return
        # Chercher initramfs compatible (même date ou plus récent)
        scanner2 = KernelScanner(self._scanner.boot)
        init_list = scanner2.initramfs_for_kernel(k)
        if init_list:
            best_init = init_list[0]
            initrd_link = self._scanner.boot / "initrd.img"
            rel_i = Path("images") / "initramfs" / best_init.filename
            try:
                initrd_link.unlink(missing_ok=True)
                initrd_link.symlink_to(str(rel_i))
                log.write_line(f"  ✅ initrd.img → {best_init.filename}")
            except Exception as exc:
                log.write_line(f"  ⚠  initrd.img : {exc}")
        else:
            log.write_line("  ⚠  aucun initramfs compatible — initrd.img non mis à jour")
        # Modules
        if k.has_modules and k.modules_path:
            mod_link = self._scanner.boot / "modules.sfs"
            rel_m = Path("images") / "modules" / k.modules_path.name
            try:
                mod_link.unlink(missing_ok=True)
                mod_link.symlink_to(str(rel_m))
                log.write_line(f"  ✅ modules.sfs → {k.modules_path.name}")
            except Exception as exc:
                log.write_line(f"  ⚠  modules.sfs : {exc}")
        # Mettre à jour config.sh
        cfg = ConfigManager()
        if cfg.get_path():
            cfg.set("KERNEL_LABEL", k.label)
            if k.kver:
                cfg.set("KERNEL_VER", k.kver)
            log.write_line(f"  ✅ config.sh mis à jour  KERNEL_LABEL={k.label}")
        self._reload()

    @on(Button.Pressed, "#btn-ks-delete")
    def do_delete(self) -> None:
        k = self._sel_kernel()
        if not k:
            self.query_one("#ks-log", Log).write_line("⚠  Sélectionnez un kernel")
            return
        if k.is_active:
            self.query_one("#ks-log", Log).write_line(
                "❌ Impossible de supprimer le kernel actif (désactivez-le d'abord)"
            )
            return
        log = self.query_one("#ks-log", Log)
        mgr = KernelInstallManager(self._scanner.boot)
        ok2, msg = mgr.delete(k)
        log.write_line(f"{'✅' if ok2 else '❌'}  {msg}")
        if ok2:
            self._reload()

    @on(Button.Pressed, "#btn-ks-install")
    def do_install(self) -> None:
        self.app.push_screen(
            KernelInstallScreen(boot=self._scanner.boot),
            callback=lambda _: self._reload()
        )


# =============================================================================
# KernelInstallScreen — Installation d'un kernel depuis le live
# =============================================================================
class KernelInstallScreen(Screen):
    BINDINGS = [Binding("escape", "app.pop_screen", "Retour")]

    def __init__(self, boot: Path | None = None) -> None:
        super().__init__()
        self._boot = boot or BootPoolLocator.find() or _ZBM_LIVE_ROOT
        self._mgr  = KernelInstallManager(self._boot)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("📥  INSTALLATION KERNEL  —  depuis le système live", classes="screen-title")
        with Vertical(id="ki-form"):
            yield Static("Label du kernel", classes="field-label")
            yield Input(id="ki-label",
                        placeholder="ex: generic-6.12  custom-i5-6.12",
                        value=ConfigManager().kernel_label)
            yield Static("Source kernel (vide = auto-détection depuis le live)", classes="field-label")
            yield Input(id="ki-src", placeholder="ex: /boot/vmlinuz-6.12.0-4-amd64  (vide = auto)")
            yield Static("Source modules (vide = auto-détection depuis le live)", classes="field-label")
            yield Input(id="ki-mod", placeholder="ex: /lib/modules/6.12.0-4-amd64  (vide = auto)")
            with Horizontal():
                yield Button("📥 Installer", variant="success", id="btn-ki-install")
                yield Button("🔍 Détecter sources", variant="primary", id="btn-ki-detect")
                yield Button("🔙 Annuler", variant="default", id="btn-ki-cancel")
            yield Log(id="ki-log", auto_scroll=True)
        yield Footer()

    @on(Button.Pressed, "#btn-ki-cancel")
    def go_back(self) -> None:
        self.app.pop_screen()

    @on(Button.Pressed, "#btn-ki-detect")
    def do_detect(self) -> None:
        log = self.query_one("#ki-log", Log)
        log.clear()
        log.write_line("🔍 Recherche kernel + modules dans le live ...")
        self._run_detect()

    @work(thread=True)
    def _run_detect(self) -> None:
        log = self.query_one("#ki-log", Log)
        mgr = self._mgr

        def w(line: str) -> None:
            self.app.call_from_thread(log.write_line, line)

        k = mgr.find_kernel_in_live()
        if k:
            self.app.call_from_thread(lambda: setattr(self.query_one("#ki-src", Input), 'value', str(k)))
            w(f"  ✅ Kernel : {k}")
            kname = k.name
            kver = re.sub(r'^vmlinuz-?', '', kname) or "unknown"
            m = mgr.find_modules_in_live(kver)
            if m:
                self.app.call_from_thread(lambda: setattr(self.query_one("#ki-mod", Input), 'value', str(m)))
                w(f"  ✅ Modules : {m}")
            else:
                w("  ⚠  Modules non trouvés")
            label_val = f"generic-{kver.split('-')[0] if kver != 'unknown' else '6.x'}"
            def _set_label() -> None:
                inp = self.query_one("#ki-label", Input)
                if not inp.value:
                    inp.value = label_val
            self.app.call_from_thread(_set_label)
        else:
            w("  ❌ Kernel non trouvé dans le live")

    @on(Button.Pressed, "#btn-ki-install")
    def do_install(self) -> None:
        label = self.query_one("#ki-label", Input).value.strip()
        src_raw = self.query_one("#ki-src", Input).value.strip()
        mod_raw = self.query_one("#ki-mod", Input).value.strip()
        log = self.query_one("#ki-log", Log)
        log.clear()
        if not label:
            log.write_line("❌ Label requis"); return
        self._run_install(label, src_raw, mod_raw)

    @work(thread=True)
    def _run_install(self, label: str, src_raw: str, mod_raw: str) -> None:
        log = self.query_one("#ki-log", Log)
        mgr = self._mgr

        def w(line: str) -> None:
            self.app.call_from_thread(log.write_line, line)

        kernel_src  = Path(src_raw)  if src_raw  else None
        modules_src = Path(mod_raw)  if mod_raw  else None

        gen = mgr.install(label=label, kernel_src=kernel_src, modules_src=modules_src)
        result = None
        try:
            while True:
                w(next(gen))
        except StopIteration as e:
            result = e.value

        if result:
            ok2, msg = result
            w(f"\n{'✅' if ok2 else '❌'}  {msg}")


# =============================================================================
# DeployScreen — Tableau de bord du déploiement
# Équivalent Python de deploy.sh — toutes les étapes accessibles depuis la TUI
# =============================================================================
class DeployScreen(Screen):
    """Tableau de bord de déploiement — miroir Python de deploy.sh.
    Étapes accessibles en un clic, log en temps réel, état global.
    """
    BINDINGS = [Binding("escape", "app.pop_screen", "Retour"),
                Binding("r", "refresh_all", "Rafraîchir")]

    def __init__(self) -> None:
        super().__init__()
        self._cfg    = ConfigManager()
        self._orch   = DeployOrchestrator()
        self._dm     = DatasetManager()
        self._pm_mgr = PoolManager()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("🚀  DÉPLOIEMENT  —  Toutes les étapes", classes="screen-title")
        with Horizontal(id="dp-layout"):
            # Colonne gauche : état et étapes
            with Vertical(id="dp-left"):
                yield Static("État global", classes="panel-title")
                yield DataTable(id="dp-status-table", cursor_type="none")
                yield Static("Étapes de déploiement", classes="panel-title")
                with Vertical(id="dp-steps"):
                    yield Button("1 · Détecter l'environnement",     variant="primary", id="btn-dp-1",
                                 tooltip="Scan NVMe, pools ZFS, config.sh")
                    yield Button("2 · Vérifier datasets ZFS",         variant="primary", id="btn-dp-2",
                                 tooltip="Vérifie et crée les datasets manquants")
                    yield Button("3 · ⚙  Kernels installés",          variant="warning", id="btn-dp-3",
                                 tooltip="Liste, sélectionne, installe un kernel")
                    yield Button("4 · 📦 Initramfs",                  variant="primary", id="btn-dp-4",
                                 tooltip="Construit un initramfs (zbm/zbm-stream/minimal)")
                    yield Button("5 · 💿 Rootfs",                     variant="primary", id="btn-dp-5",
                                 tooltip="Installe un rootfs squashfs dans boot_pool")
                    yield Button("7 · 📋 Presets de boot",            variant="primary", id="btn-dp-7",
                                 tooltip="Génère les presets JSON")
                    yield Button("8 · Failsafe",                      variant="default", id="btn-dp-8",
                                 tooltip="Crée / met à jour le failsafe")
                    yield Static("─────────────────────────────", classes="section-sep")
                    yield Button("9 · ✅ Statut complet",             variant="success", id="btn-dp-9",
                                 tooltip="Résumé de toutes les étapes")

            # Colonne droite : log + config active
            with Vertical(id="dp-right"):
                yield Static("Configuration active (config.sh)", classes="panel-title")
                yield Static(id="dp-config", classes="dp-config")
                yield Static("Log", classes="panel-title")
                yield Log(id="dp-log", auto_scroll=True)
                with Horizontal():
                    yield Button("🗑 Vider log", variant="default", id="btn-dp-clear")
                    yield Button("🔙 Retour",   variant="default", id="btn-dp-back")

        yield Footer()

    def on_mount(self) -> None:
        t = self.query_one("#dp-status-table", DataTable)
        t.add_columns("Composant", "État", "Détail")
        self._refresh_config()
        self._refresh_status_table()

    def _refresh_config(self) -> None:
        self._cfg.reload()
        systems = self._cfg.get_systems()
        lines = [
            f"  config.sh : [dim]{self._cfg.path_str}[/dim]",
            f"  SYSTEMS   : {', '.join(systems)}",
            f"  KERNEL_LABEL : {self._cfg.kernel_label or '(vide)'}",
            f"  KERNEL_VER   : {self._cfg.kernel_ver or '(vide)'}",
            f"  INIT_TYPE    : {self._cfg.init_type}",
            f"  ROOTFS_LABEL : {self._cfg.rootfs_label}",
            f"  NVME_A       : {self._cfg.nvme_a or '(non détecté)'}",
            f"  EFI_PART     : {self._cfg.efi_part or '(non détecté)'}",
        ]
        self.query_one("#dp-config", Static).update("\n".join(lines))

    def _refresh_status_table(self) -> None:
        t = self.query_one("#dp-status-table", DataTable)
        t.clear()
        # Pools
        for pool in ["boot_pool", "fast_pool", "data_pool"]:
            info = self._pm_mgr.info(pool)
            icon = "✅" if info.state == "imported" else ("⚠" if info.state == "importable" else "❌")
            detail = f"{info.health}  {info.size}" if info.state == "imported" else info.state
            t.add_row(pool, f"{icon} {info.state}", detail)
        # Kernels
        scanner = KernelScanner()
        kernels = scanner.scan()
        k_detail = f"{len(kernels)} kernel(s)" + (f"  [{kernels[0].kver}]" if kernels else "")
        t.add_row("kernels", "✅" if kernels else "❌", k_detail)
        # Initramfs
        ib = InitramfsBuilder()
        imgs = ib.list_available()
        t.add_row("initramfs", "✅" if imgs else "❌", f"{len(imgs)} initramfs")
        # Rootfs
        rootfs = NamingHelper.list_images("rootfs")
        t.add_row("rootfs", "✅" if rootfs else "⚠", f"{len(rootfs)} rootfs")
        # Presets
        presets = list(PRESETS_DIR.glob("*.json")) if PRESETS_DIR.exists() else []
        t.add_row("presets", "✅" if presets else "❌", f"{len(presets)} presets")

    def _log(self, msg: str) -> None:
        self.query_one("#dp-log", Log).write_line(msg)

    def _run_gen(self, gen: "Generator[str, None, tuple[bool, str]]") -> None:
        """Délègue vers _run_step_work — conservé pour compatibilité interne."""
        self._run_step_work_gen(gen)

    @work(thread=True)
    def _run_step_work_gen(self, gen: "Generator[str, None, tuple[bool, str]]") -> None:
        log = self.query_one("#dp-log", Log)
        self.app.call_from_thread(log.clear)
        def w(line: str) -> None:
            self.app.call_from_thread(log.write_line, line)
        result = None
        try:
            while True: w(next(gen))
        except StopIteration as e:
            result = e.value
        if result:
            ok2, detail = result
            w(f"\n{'✅' if ok2 else '❌'}  {detail}")
            if ok2:
                self.app.call_from_thread(self._refresh_status_table)
                self.app.call_from_thread(self._refresh_config)

    @on(Button.Pressed, "#btn-dp-back")
    def go_back(self) -> None:
        self.app.pop_screen()

    @on(Button.Pressed, "#btn-dp-clear")
    def do_clear(self) -> None:
        self.query_one("#dp-log", Log).clear()

    def action_refresh_all(self) -> None:
        self._refresh_status_table()
        self._refresh_config()
        self._log("✅ Rafraîchi")

    @on(Button.Pressed, "#btn-dp-1")
    def do_step1(self) -> None: self._run_step_work("detect")

    @on(Button.Pressed, "#btn-dp-2")
    def do_step2(self) -> None: self._run_step_work("datasets")

    @on(Button.Pressed, "#btn-dp-3")
    def do_step3(self) -> None:
        """Ouvre KernelSelectScreen — liste + sélection des kernels."""
        self.app.push_screen(
            KernelSelectScreen(),
            callback=lambda _: (self._refresh_status_table(), self._refresh_config())
        )

    @on(Button.Pressed, "#btn-dp-4")
    def do_step4(self) -> None:
        self.app.push_screen(InitramfsScreen())

    @on(Button.Pressed, "#btn-dp-5")
    def do_step5(self) -> None:
        self.app.push_screen(RootfsScreen())

    @on(Button.Pressed, "#btn-dp-7")
    def do_step7(self) -> None: self._run_step_work("presets")

    @on(Button.Pressed, "#btn-dp-8")
    def do_step8(self) -> None:
        self._log("⛑  Failsafe → voir écran Failsafe (bouton principal)")

    @on(Button.Pressed, "#btn-dp-9")
    def do_step9(self) -> None:
        def confirmed(yes: bool) -> None:
            if yes:
                self._run_step_work("full")
        self.app.push_screen(
            _ConfirmScreen("Lancer toutes les étapes (1→7) en séquence ?"),
            callback=confirmed
        )

    @work(thread=True)
    def _run_step_work(self, step: str) -> None:
        log = self.query_one("#dp-log", Log)
        self.app.call_from_thread(log.clear)

        def w(line: str) -> None:
            self.app.call_from_thread(log.write_line, line)

        systems = self._cfg.get_systems()
        if step == "detect":
            gen = self._orch.step_detect()
        elif step == "datasets":
            gen = self._orch.step_datasets(systems)
        elif step == "presets":
            gen = self._orch.step_presets_info()
        else:
            gen = self._orch.full_status(systems)

        result = None
        try:
            while True:
                w(next(gen))
        except StopIteration as e:
            result = e.value

        if result:
            ok2, detail = result
            w(f"\n{'✅' if ok2 else '❌'}  {detail}")
            if ok2:
                self.app.call_from_thread(self._refresh_status_table)
                self.app.call_from_thread(self._refresh_config)


# =============================================================================
# InitramfsScreen — Construction d'un initramfs depuis la TUI
# =============================================================================
class InitramfsScreen(Screen):
    BINDINGS = [Binding("escape", "app.pop_screen", "Retour")]

    def __init__(self) -> None:
        super().__init__()
        self._builder = InitramfsBuilder()
        self._scanner = KernelScanner()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("📦  CONSTRUCTION INITRAMFS", classes="screen-title")
        with Vertical(id="if-form"):
            yield Static("Type d'initramfs", classes="field-label")
            yield Select(
                [(v, k) for k, v in InitramfsBuilder.INIT_TYPES.items()],
                id="if-type", value="zbm",
            )
            yield Static(
                "kver cible (uniquement pour type 'minimal')", classes="field-label"
            )
            cfg = ConfigManager()
            yield Input(id="if-kver", value=cfg.kernel_ver,
                        placeholder="ex: 6.12.0-4-amd64  (auto si kernel installé)")

            yield Static("Initramfs existants dans boot_pool", classes="panel-title")
            yield ListView(id="if-list")

            with Horizontal():
                yield Button("🔨 Construire", variant="success",  id="btn-if-build")
                yield Button("🗑 Supprimer",  variant="error",    id="btn-if-delete")
                yield Button("🔙 Retour",     variant="default",  id="btn-if-back")
            yield Log(id="if-log", auto_scroll=True)
        yield Footer()

    def on_mount(self) -> None:
        self._reload_list()

    def _reload_list(self) -> None:
        self._do_reload_list()

    @work(thread=True)
    def _do_reload_list(self) -> None:
        imgs = self._builder.list_available()
        def update() -> None:
            lv = self.query_one("#if-list", ListView)
            lv.clear()
            if not imgs:
                lv.append(ListItem(Label("  (aucun initramfs installé)"), name=""))
            for img in imgs:
                meta = NamingHelper.read_meta(img.path)
                it   = meta.get("init_type", img.label)
                kv   = meta.get("kernel_ver", "?")
                sz   = human_size(img.path.stat().st_size) if img.path.exists() else "?"
                lv.append(ListItem(
                    Label(f"{img.filename}  [dim]{it}  kver={kv}  {sz}[/dim]"),
                    name=str(img.path)
                ))
        self.app.call_from_thread(update)

    @on(Button.Pressed, "#btn-if-back")
    def go_back(self) -> None:
        self.app.pop_screen()

    @on(Button.Pressed, "#btn-if-build")
    def do_build(self) -> None:
        sel = self.query_one("#if-type", Select)
        init_type = str(sel.value) if sel.value != Select.BLANK else "zbm"
        kver = self.query_one("#if-kver", Input).value.strip()
        log = self.query_one("#if-log", Log)
        log.clear()

        if init_type == "minimal" and not kver:
            latest = self._scanner.latest_kernel()
            if latest and latest.kver:
                kver = latest.kver
                log.write_line(f"  kver auto depuis kernel installé : {kver}")
            else:
                log.write_line("  ❌ kver requise pour type minimal — installez d'abord un kernel")
                return

        self._run_build(init_type, kver)

    @work(thread=True)
    def _run_build(self, init_type: str, kver: str) -> None:
        log = self.query_one("#if-log", Log)

        def w(line: str) -> None:
            self.app.call_from_thread(log.write_line, line)

        gen = self._builder.build(init_type, kver_for_minimal=kver)
        result = None
        try:
            while True:
                w(next(gen))
        except StopIteration as e:
            result = e.value

        if result:
            ok2, msg = result
            w(f"\n{'✅' if ok2 else '❌'}  {msg}")
            if ok2:
                self.app.call_from_thread(self._reload_list)

    @on(Button.Pressed, "#btn-if-delete")
    def do_delete(self) -> None:
        lv = self.query_one("#if-list", ListView)
        if lv.index is None:
            return
        try:
            item = lv.highlighted_child
            if item is None: return
            p = Path(item.name)
        except Exception:
            return
        if not p or not p.exists():
            return
        log = self.query_one("#if-log", Log)
        try:
            p.unlink()
            Path(str(p) + ".meta").unlink(missing_ok=True)
            log.write_line(f"✅ Supprimé : {p.name}")
            self._reload_list()
        except Exception as exc:
            log.write_line(f"❌ {exc}")


# =============================================================================
# RootfsScreen — Installation d'un rootfs squashfs depuis la TUI
# =============================================================================
class RootfsScreen(Screen):
    BINDINGS = [Binding("escape", "app.pop_screen", "Retour")]

    def __init__(self) -> None:
        super().__init__()
        self._rim = RootfsInstallManager()
        self._cfg = ConfigManager()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("💿  INSTALLATION ROOTFS", classes="screen-title")
        with Vertical(id="rf-form"):
            yield Static("Rootfs disponibles (live + boot_pool)", classes="panel-title")
            yield ListView(id="rf-available")
            yield Static("Système cible", classes="field-label")
            yield Input(id="rf-system", value=self._cfg.get_systems()[0],
                        placeholder="ex: systeme1")
            yield Static("Label", classes="field-label")
            yield Input(id="rf-label", value=self._cfg.rootfs_label,
                        placeholder="ex: gentoo  arch  debian-base")
            yield Static("Chemin source (ou sélectionner ci-dessus)", classes="field-label")
            yield Input(id="rf-src", placeholder="ex: /run/live/medium/live/filesystem.squashfs")
            with Horizontal():
                yield Button("📥 Installer", variant="success", id="btn-rf-install")
                yield Button("🔙 Retour",   variant="default", id="btn-rf-back")
            yield Log(id="rf-log", auto_scroll=True)
        yield Footer()

    def on_mount(self) -> None:
        self._reload_available()

    def _reload_available(self) -> None:
        self._do_reload_available()

    @work(thread=True)
    def _do_reload_available(self) -> None:
        found = self._rim.find_rootfs_on_live()
        def update() -> None:
            lv = self.query_one("#rf-available", ListView)
            lv.clear()
            if not found:
                lv.append(ListItem(Label("  (aucun rootfs trouvé)"), name=""))
            for p in found:
                sz = human_size(p.stat().st_size) if p.exists() else "?"
                lv.append(ListItem(Label(f"{p}  [dim]{sz}[/dim]"), name=str(p)))
        self.app.call_from_thread(update)

    @on(ListView.Selected, "#rf-available")
    def on_src_selected(self, ev: ListView.Selected) -> None:
        if ev.item.name:
            self.query_one("#rf-src", Input).value = ev.item.name

    @on(Button.Pressed, "#btn-rf-back")
    def go_back(self) -> None:
        self.app.pop_screen()

    @on(Button.Pressed, "#btn-rf-install")
    def do_install(self) -> None:
        src_raw = self.query_one("#rf-src", Input).value.strip()
        system  = self.query_one("#rf-system", Input).value.strip()
        label   = self.query_one("#rf-label", Input).value.strip()
        log = self.query_one("#rf-log", Log)
        log.clear()
        if not src_raw:
            log.write_line("❌ Chemin source requis"); return
        if not system:
            log.write_line("❌ Système requis"); return
        if not label:
            log.write_line("❌ Label requis"); return
        self._run_rf_install(src_raw, system, label)

    @work(thread=True)
    def _run_rf_install(self, src_raw: str, system: str, label: str) -> None:
        log = self.query_one("#rf-log", Log)
        def w(line: str) -> None:
            self.app.call_from_thread(log.write_line, line)
        gen = self._rim.install(Path(src_raw), system, label)
        result = None
        try:
            while True:
                w(next(gen))
        except StopIteration as e:
            result = e.value
        if result:
            ok2, msg = result
            w(f"\n{'✅' if ok2 else '❌'}  {msg}")


# =============================================================================
# APPLICATION
# =============================================================================
class ZBMApp(App):
    TITLE     = "ZFSBootMenu Manager"
    SUB_TITLE = "i5-11400 / Z490 UD / Gentoo"
    BINDINGS  = [Binding("ctrl+q","quit","Quitter")]

    CSS = """
    Screen          { background: $surface; }
    .screen-title   { text-align:center; text-style:bold; background:$primary;
                      color:$text; padding:1; margin-bottom:1; }
    .panel-title    { text-style:bold; color:$accent; padding:1 2 0 2; }
    .active-info    { padding:0 2; color:$success; }
    .field-label    { padding:1 0 0 0; text-style:bold; }
    .snap-preview   { padding:1; margin:1 0; border:solid $accent;
                      background:$surface-darken-1; }
    .spacer         { height:1; }

    #layout         { height:1fr; }
    #left           { width:36; border-right:solid $primary-darken-2; padding:0 1; }
    #right          { width:1fr; padding:0 2; }
    #preset-detail  { height:13; border:solid $primary-darken-2; padding:1; margin-bottom:1; }
    #stream-bar     { height:3; border:solid $accent-darken-2; padding:0 1; margin-bottom:1; }
    #main-actions   { height:auto; margin-bottom:1; }
    #main-actions Button { margin-right:1; }
    #status-bar     { height:3; border:solid $primary-darken-3; padding:0 1; margin-bottom:1; }
    #link-table     { height:10; border:solid $primary-darken-2; }

    /* Stream */
    #stream-status-bar  { height:3; border:solid $accent; padding:0 1; margin-bottom:1; }
    #stream-btns        { height:auto; margin-bottom:1; }
    #stream-btns Button { margin-right:1; }
    #stream-config      { height:auto; margin-bottom:1; }
    #stream-config Vertical { width:1fr; padding:0 1; }
    #stream-log         { height:1fr; border:solid $primary-darken-2; }

    /* Snapshot */
    #snap-layout { height:1fr; }
    #snap-left   { width:38; border-right:solid $primary-darken-2; padding:0 1; }
    #snap-right  { width:1fr; padding:0 1; }
    #sets-table  { height:12; border:solid $primary-darken-2; margin-bottom:1; }
    #snap-log    { height:1fr; border:solid $primary-darken-3; }

    /* Cohérence */
    #coh-top    { height:5; margin-bottom:1; }
    #coh-top Select { width:30; }
    #coh-top Input  { width:20; }
    #coh-top Button { margin-left:1; }
    #coh-log    { height:18; border:solid $primary-darken-2; margin-bottom:1; }
    #coh-table  { height:1fr; border:solid $primary-darken-2; }

    /* Hot-Swap */
    #hs-layout  { height:1fr; }
    #hs-left    { width:35; border-right:solid $primary-darken-2; padding:0 1; overflow-y:auto; }
    #hs-right   { width:1fr; padding:0 2; }
    .hs-current { border:solid $accent; padding:1; margin-bottom:1; height:6; }
    .section-sep { color:$primary-lighten-2; margin-top:1; margin-bottom:0; }
    #hs-log     { height:1fr; border:solid $primary-darken-3; margin-top:1; }
    #hs-cmdline { margin-bottom:1; }

    /* Forms */
    #form { padding:1 2; }

    /* Kernel Select */
    #ks-layout  { height:1fr; }
    #ks-left    { width:42; border-right:solid $primary-darken-2; padding:0 1; }
    #ks-right   { width:1fr; padding:0 2; }
    #ks-kernel-list { height:1fr; }
    #ks-btns    { height:auto; margin-top:1; }
    #ks-btns Button { margin-right:1; }
    .ks-detail  { height:16; border:solid $primary-darken-2; padding:1; margin-bottom:1; }

    /* Kernel Install */
    #ki-form    { padding:1 2; }
    #ki-log     { height:1fr; min-height:8; border:solid $primary-darken-3; margin-top:1; }

    /* Deploy Screen */
    #dp-layout  { height:1fr; }
    #dp-left    { width:46; border-right:solid $primary-darken-2; padding:0 1; }
    #dp-right   { width:1fr; padding:0 2; }
    #dp-status-table { height:10; border:solid $primary-darken-2; margin-bottom:1; }
    #dp-steps Button { width:44; margin-bottom:0; }
    .dp-config  { height:10; border:solid $accent-darken-2; padding:1; margin-bottom:1; }
    #dp-log     { height:1fr; border:solid $primary-darken-3; }

    /* Initramfs Screen */
    #if-form    { padding:1 2; }
    #if-list    { height:8; border:solid $primary-darken-2; margin-bottom:1; }

    /* Rootfs Screen */
    #rf-form    { padding:1 2; }
    #rf-available { height:8; border:solid $primary-darken-2; margin-bottom:1; }

    /* Confirm dialog */
    _ConfirmScreen          { align: center middle; }
    #confirm-box            { width: 60; height: auto; padding: 2 3;
                              border: double $accent; background: $surface;
                              align: center middle; }
    #confirm-msg            { text-align: center; padding: 1 0 2 0;
                              text-style: bold; }
    #confirm-btns           { height: auto; align: center middle; }
    #confirm-btns Button    { margin: 0 2; width: 16; }
    """

    def on_mount(self) -> None: self.push_screen(MainScreen())


if __name__ == "__main__":
    if os.geteuid() != 0:
        print("Root requis.")
        sys.exit(1)
    ZBMApp().run()
