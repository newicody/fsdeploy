"""
fsdeploy.core.detection.dataset
================================
Détecte le rôle de chaque dataset ZFS en montant temporairement
chaque dataset en mode legacy et en inspectant son contenu.

Aucun nom de pool, de dataset ou de chemin n'est codé en dur.
Le système comprend ce qu'il voit.

Rôles détectés :
    kernel          — contient des images vmlinuz / bzImage
    modules         — contient /lib/modules/<version>/ ou modules.dep
    rootfs          — arborescence système complète (bin/etc/lib)
    initramfs       — images cpio (.img / .cpio / initrd*)
    squashfs        — fichiers .sfs / .squashfs (rôle précisé dans sub_role)
    boot            — partition/dataset de boot (EFI/ ou grub/ ou kernel+initrd mélangés)
    efi             — contient EFI/BOOT/ ou *.EFI
    python_env      — venv Python ou lib/pythonX.Y/site-packages
    stream          — scripts de stream YouTube (ffmpeg, youtube-dl, streamlink…)
    data            — home/, documents, pas de rôle système reconnu
    overlay_upper   — répertoire upper OverlayFS (présence de .wh. ou structure upper)
    snapshot_store  — archives .zst / .zfs de snapshots
    unknown         — rien de reconnu

Un dataset peut avoir plusieurs rôles (ex: boot + kernel + initramfs).
"""

from __future__ import annotations

import os
import re
import stat
import subprocess
import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from fsdeploy.config import FsDeployConfig


# =============================================================================
# PATTERNS DE RECONNAISSANCE
# Chaque pattern est (glob_relatif_au_point_de_montage, rôle, priorité, note)
# On construit un arbre de décision par inspection de fichiers réels.
# =============================================================================

@dataclass
class Pattern:
    """Un motif de reconnaissance de fichier ou répertoire."""
    # Chemin relatif glob (ex: "boot/vmlinuz*") ou regex sur le chemin relatif
    glob: str | None = None
    regex: str | None = None
    # Rôle principal assigné si ce motif matche
    role: str = "unknown"
    # Sous-rôle (précise le type de squashfs, etc.)
    sub_role: str = ""
    # Priorité (plus haut = plus décisif)
    priority: int = 1
    # Note humaine sur ce qui a été trouvé
    note: str = ""
    # Vrai si la présence de ce fichier suffit à assigner le rôle
    conclusive: bool = False


# Patterns classés par priorité décroissante.
# On cherche d'abord les signaux les plus forts.
PATTERNS: list[Pattern] = [

    # ── EFI ──────────────────────────────────────────────────────────────────
    Pattern(glob="EFI/BOOT/BOOTX64.EFI",       role="efi",       priority=10, conclusive=True,
            note="EFI BOOT standard"),
    Pattern(glob="EFI/ZBM/*.EFI",              role="efi",       priority=10, conclusive=True,
            note="ZFSBootMenu EFI"),
    Pattern(glob="EFI/**/*.EFI",               role="efi",       priority=9,
            note="Binaire EFI"),
    Pattern(glob="EFI/",                       role="efi",       priority=8,
            note="Répertoire EFI"),

    # ── Kernel ───────────────────────────────────────────────────────────────
    Pattern(glob="vmlinuz",                    role="kernel",    priority=10, conclusive=True,
            note="Kernel symlink standard"),
    Pattern(glob="vmlinuz-*",                  role="kernel",    priority=10, conclusive=True,
            note="Kernel versionné"),
    Pattern(glob="bzImage",                    role="kernel",    priority=10, conclusive=True,
            note="Kernel bzImage brut"),
    Pattern(glob="boot/vmlinuz-*",             role="kernel",    priority=9,
            note="Kernel dans /boot"),
    Pattern(glob="boot/bzImage",               role="kernel",    priority=9,
            note="bzImage dans /boot"),
    Pattern(glob="images/kernels/vmlinuz-*",   role="kernel",    priority=9,
            note="Kernel dans images/kernels/"),
    Pattern(glob="images/kernels/kernel-*",    role="kernel",    priority=9,
            note="Kernel dans images/kernels/"),

    # ── Modules ──────────────────────────────────────────────────────────────
    Pattern(glob="lib/modules/*/modules.dep",  role="modules",   priority=10, conclusive=True,
            note="modules.dep trouvé"),
    Pattern(glob="lib/modules/*/kernel/",      role="modules",   priority=10, conclusive=True,
            note="Arborescence kernel/ de modules"),
    Pattern(glob="lib/modules/*/",             role="modules",   priority=8,
            note="Répertoire de version de modules"),

    # ── Initramfs ────────────────────────────────────────────────────────────
    Pattern(glob="initramfs-*",                role="initramfs", priority=10, conclusive=True,
            note="Image initramfs versionnée"),
    Pattern(glob="initrd*",                    role="initramfs", priority=10, conclusive=True,
            note="Image initrd"),
    Pattern(glob="initramfs.img",              role="initramfs", priority=10, conclusive=True,
            note="initramfs.img standard"),
    Pattern(glob="boot/initramfs-*",           role="initramfs", priority=9,
            note="Initramfs dans /boot"),
    Pattern(glob="images/initramfs/initramfs-*", role="initramfs", priority=9,
            note="Initramfs dans images/"),

    # ── Squashfs ─────────────────────────────────────────────────────────────
    Pattern(glob="*.sfs",                      role="squashfs",  priority=9,  conclusive=True,
            note="Image squashfs .sfs"),
    Pattern(glob="*.squashfs",                 role="squashfs",  priority=9,  conclusive=True,
            note="Image squashfs .squashfs"),
    Pattern(glob="images/rootfs/*.sfs",        role="squashfs",  sub_role="rootfs",   priority=10,
            note="Rootfs squashfs"),
    Pattern(glob="images/modules/*.sfs",       role="squashfs",  sub_role="modules",  priority=10,
            note="Modules squashfs"),
    Pattern(glob="images/startup/*.sfs",       role="squashfs",  sub_role="python",   priority=10,
            note="Python squashfs"),
    Pattern(glob="rootfs*.sfs",                role="squashfs",  sub_role="rootfs",   priority=9,
            note="Rootfs squashfs à la racine"),
    Pattern(glob="modules*.sfs",               role="squashfs",  sub_role="modules",  priority=9,
            note="Modules squashfs à la racine"),
    Pattern(glob="python*.sfs",                role="squashfs",  sub_role="python",   priority=9,
            note="Python squashfs à la racine"),

    # ── Rootfs complet ────────────────────────────────────────────────────────
    Pattern(glob="bin/sh",                     role="rootfs",    priority=8,
            note="/bin/sh présent"),
    Pattern(glob="usr/bin/python3",            role="rootfs",    priority=8,
            note="Python dans rootfs"),
    Pattern(glob="etc/os-release",             role="rootfs",    priority=9, conclusive=True,
            note="os-release — rootfs identifié"),
    Pattern(glob="etc/fstab",                  role="rootfs",    priority=8,
            note="fstab — rootfs probable"),
    Pattern(glob="usr/lib/os-release",         role="rootfs",    priority=9,
            note="usr/lib/os-release — rootfs"),

    # ── Python env ────────────────────────────────────────────────────────────
    Pattern(glob="venv/bin/python3",           role="python_env", priority=10, conclusive=True,
            note="venv Python"),
    Pattern(glob="venv/bin/activate",          role="python_env", priority=10, conclusive=True,
            note="venv activate"),
    Pattern(glob="lib/python*/site-packages/textual/",
                                               role="python_env", priority=10, conclusive=True,
            note="Textual installé"),
    Pattern(glob="lib/python*/site-packages/", role="python_env", priority=7,
            note="site-packages Python"),
    Pattern(glob="bin/python3",                role="python_env", priority=6,
            note="python3 dans bin/"),

    # ── Stream ────────────────────────────────────────────────────────────────
    Pattern(glob="**/stream*.py",             role="stream",    priority=9,
            note="Script stream Python"),
    Pattern(glob="**/youtube*.py",            role="stream",    priority=9,
            note="Script YouTube Python"),
    Pattern(glob="bin/ffmpeg",                role="stream",    priority=8,
            note="ffmpeg présent"),
    Pattern(glob="usr/bin/ffmpeg",            role="stream",    priority=8,
            note="ffmpeg dans /usr/bin"),

    # ── Boot (mix kernel+initramfs+grub) ─────────────────────────────────────
    Pattern(glob="grub/grub.cfg",             role="boot",      priority=9, conclusive=True,
            note="GRUB config"),
    Pattern(glob="grub2/grub.cfg",            role="boot",      priority=9, conclusive=True,
            note="GRUB2 config"),
    Pattern(glob="presets/",                  role="boot",      priority=7,
            note="Répertoire presets (boot_pool)"),
    Pattern(glob="presets/*.json",            role="boot",      priority=8,
            note="Presets JSON (boot_pool)"),
    Pattern(glob="EFI/ZBM/config.yaml",       role="boot",      priority=10, conclusive=True,
            note="ZFSBootMenu config"),

    # ── Overlay upper ────────────────────────────────────────────────────────
    Pattern(glob="upper/",                    role="overlay_upper", priority=8,
            note="Répertoire upper/ OverlayFS"),
    Pattern(glob="work/",                     role="overlay_upper", priority=5,
            note="Répertoire work/ OverlayFS"),

    # ── Snapshots ────────────────────────────────────────────────────────────
    Pattern(glob="**/*.zst",                  role="snapshot_store", priority=7,
            note="Archive .zst"),
    Pattern(glob="**/snap.meta",              role="snapshot_store", priority=9, conclusive=True,
            note="Métadonnées snapshot fsdeploy"),

    # ── Data ─────────────────────────────────────────────────────────────────
    Pattern(glob="home/",                     role="data",      priority=6,
            note="Répertoire home/"),
    Pattern(glob="home/*/",                   role="data",      priority=7,
            note="Répertoires utilisateurs"),
]


# =============================================================================
# RÉSULTAT D'ANALYSE D'UN DATASET
# =============================================================================

@dataclass
class DatasetFinding:
    """Résultat de l'analyse d'un dataset."""

    # Identité
    dataset: str                    # nom complet : pool/path/to/dataset
    pool: str                       # nom du pool
    mountpoint_zfs: str             # mountpoint ZFS déclaré (peut être "none"/"legacy")
    used: str                       # espace utilisé
    avail: str                      # espace disponible
    creation: str                   # date de création ZFS

    # Analyse de contenu
    roles: list[str] = field(default_factory=list)
    # Détail des matches : {role: [note, ...]}
    evidence: dict[str, list[str]] = field(default_factory=dict)
    # Fichiers remarquables trouvés (max ~20)
    notable_files: list[str] = field(default_factory=list)
    # Versions détectées (kernel, python, os…)
    versions: dict[str, str] = field(default_factory=dict)
    # OS détecté si rootfs
    os_info: dict[str, str] = field(default_factory=dict)

    # Montage temporaire
    probe_mount: str = ""           # chemin utilisé pour la sonde
    probe_error: str = ""           # erreur éventuelle lors du montage

    # Score de confiance global (0-100)
    confidence: int = 0

    # Montage suggéré (calculé après analyse)
    suggested_mount: str = ""

    @property
    def primary_role(self) -> str:
        """Rôle principal (priorité aux rôles les plus significatifs)."""
        priority_order = [
            "efi", "boot", "kernel", "modules", "initramfs",
            "squashfs", "rootfs", "python_env", "stream",
            "overlay_upper", "snapshot_store", "data", "unknown",
        ]
        for r in priority_order:
            if r in self.roles:
                return r
        return "unknown"

    @property
    def is_empty(self) -> bool:
        return not self.roles or self.roles == ["unknown"]

    def add_evidence(self, role: str, note: str) -> None:
        if role not in self.roles:
            self.roles.append(role)
        self.evidence.setdefault(role, [])
        if note not in self.evidence[role]:
            self.evidence[role].append(note)

    def to_dict(self) -> dict:
        return {
            "dataset":        self.dataset,
            "pool":           self.pool,
            "mountpoint_zfs": self.mountpoint_zfs,
            "used":           self.used,
            "avail":          self.avail,
            "creation":       self.creation,
            "roles":          self.roles,
            "primary_role":   self.primary_role,
            "evidence":       self.evidence,
            "notable_files":  self.notable_files,
            "versions":       self.versions,
            "os_info":        self.os_info,
            "confidence":     self.confidence,
            "suggested_mount": self.suggested_mount,
            "probe_error":    self.probe_error,
        }


# =============================================================================
# SONDE D'UN DATASET
# =============================================================================

class DatasetProbe:
    """
    Monte un dataset temporairement en legacy et analyse son contenu.
    Utilisé exclusivement par DatasetDetector.
    """

    PROBE_BASE = Path("/tmp/fsdeploy-probe")
    MOUNT_TIMEOUT = 10   # secondes
    # Profondeur max de scan (évite les rootfs énormes)
    MAX_DEPTH = 6
    # Nombre max de fichiers à lister dans notable_files
    MAX_NOTABLE = 30

    def __init__(self, dataset: str, pool_props: dict) -> None:
        self.dataset = dataset
        self.pool_props = pool_props
        # Nom de répertoire sûr pour le mount temporaire
        safe_name = dataset.replace("/", "_").replace(" ", "_")
        self.mount_point = self.PROBE_BASE / safe_name
        self._mounted = False

    # ── Cycle de vie ─────────────────────────────────────────────────────────

    def __enter__(self) -> "DatasetProbe":
        self._do_mount()
        return self

    def __exit__(self, *_) -> None:
        self._do_umount()

    def _do_mount(self) -> None:
        self.mount_point.mkdir(parents=True, exist_ok=True)
        try:
            r = subprocess.run(
                ["mount", "-t", "zfs", self.dataset, str(self.mount_point)],
                capture_output=True, text=True, timeout=self.MOUNT_TIMEOUT,
            )
            if r.returncode == 0:
                self._mounted = True
            else:
                # Peut déjà être monté ailleurs — on essaie de lire là où c'est monté
                current = self._find_current_mount()
                if current:
                    self.mount_point = Path(current)
                    self._mounted = False  # pas notre montage, on ne démonte pas
                # Sinon la sonde sera vide (probe_error sera rempli par le caller)
        except subprocess.TimeoutExpired:
            pass

    def _do_umount(self) -> None:
        if not self._mounted:
            return
        try:
            subprocess.run(
                ["umount", str(self.mount_point)],
                capture_output=True, timeout=self.MOUNT_TIMEOUT,
            )
        except Exception:
            # Forcer si nécessaire
            subprocess.run(
                ["umount", "-l", str(self.mount_point)],
                capture_output=True, timeout=5,
            )
        finally:
            try:
                self.mount_point.rmdir()
            except OSError:
                pass
            self._mounted = False

    def _find_current_mount(self) -> str:
        """Cherche si le dataset est déjà monté quelque part."""
        try:
            r = subprocess.run(
                ["zfs", "get", "-H", "-o", "value", "mounted,mountpoint", self.dataset],
                capture_output=True, text=True, timeout=5,
            )
            lines = r.stdout.strip().splitlines()
            if len(lines) == 2 and lines[0] == "yes":
                mp = lines[1]
                if mp not in ("none", "legacy", "-") and Path(mp).is_dir():
                    return mp
        except Exception:
            pass
        return ""

    # ── Analyse du contenu ───────────────────────────────────────────────────

    def probe(self) -> tuple[list[str], dict[str, list[str]], list[str], dict[str, str], dict[str, str], str]:
        """
        Analyse le contenu monté.
        Retourne : (roles, evidence, notable_files, versions, os_info, error)
        """
        if not self.mount_point.exists() or not any(self.mount_point.iterdir() if self._is_accessible() else []):
            return [], {}, [], {}, {}, "Dataset vide ou inaccessible"

        roles: dict[str, int] = {}        # role → score cumulé
        evidence: dict[str, list[str]] = {}
        notable_files: list[str] = []
        versions: dict[str, str] = {}
        os_info: dict[str, str] = {}

        # ── Scan des fichiers ─────────────────────────────────────────────────
        for rel_path in self._walk():
            # Appliquer chaque pattern
            for pat in PATTERNS:
                if self._match_pattern(rel_path, pat):
                    score = pat.priority * (5 if pat.conclusive else 1)
                    roles[pat.role] = roles.get(pat.role, 0) + score
                    evidence.setdefault(pat.role, [])
                    note = f"{pat.note} ({rel_path})"
                    if note not in evidence[pat.role]:
                        evidence[pat.role].append(note)

            # Fichiers notables
            if self._is_notable(rel_path) and len(notable_files) < self.MAX_NOTABLE:
                notable_files.append(rel_path)

        # ── Extraction de versions ────────────────────────────────────────────
        versions.update(self._extract_versions(notable_files))

        # ── Lecture os-release ────────────────────────────────────────────────
        os_info.update(self._read_os_release())

        # ── Calcul des rôles finaux (seuil de score) ─────────────────────────
        # Un rôle est retenu si son score dépasse un seuil minimal
        SCORE_THRESHOLD = 3
        final_roles = [r for r, s in sorted(roles.items(), key=lambda x: -x[1])
                       if s >= SCORE_THRESHOLD]

        if not final_roles:
            final_roles = ["unknown"]

        return final_roles, evidence, notable_files, versions, os_info, ""

    def _is_accessible(self) -> bool:
        try:
            next(self.mount_point.iterdir())
            return True
        except (StopIteration, PermissionError, OSError):
            return True  # vide mais accessible

    def _walk(self) -> Iterator[str]:
        """
        Parcours limité en profondeur et en nombre de fichiers.
        Yield des chemins relatifs au mount_point.
        """
        count = 0
        MAX_FILES = 2000

        def _recurse(path: Path, depth: int) -> Iterator[str]:
            nonlocal count
            if depth > self.MAX_DEPTH or count > MAX_FILES:
                return
            try:
                entries = sorted(path.iterdir())
            except (PermissionError, OSError):
                return

            for entry in entries:
                if count > MAX_FILES:
                    return
                try:
                    rel = str(entry.relative_to(self.mount_point))
                    # Yield le chemin (avec / final si répertoire)
                    if entry.is_dir(follow_symlinks=False):
                        yield rel + "/"
                        yield from _recurse(entry, depth + 1)
                    else:
                        yield rel
                    count += 1
                except (OSError, ValueError):
                    continue

        yield from _recurse(self.mount_point, 0)

    def _match_pattern(self, rel_path: str, pat: Pattern) -> bool:
        """Teste si rel_path matche le pattern (glob ou regex)."""
        if pat.glob:
            return self._glob_match(rel_path, pat.glob)
        if pat.regex:
            return bool(re.search(pat.regex, rel_path))
        return False

    def _glob_match(self, path: str, glob: str) -> bool:
        """
        Matching de glob simplifié :
          *   → n'importe quoi sauf /
          **  → n'importe quoi y compris /
          ?   → un caractère
        """
        # Normaliser
        path = path.lstrip("/")
        glob = glob.lstrip("/")

        # Convertir le glob en regex
        regex = re.escape(glob)
        regex = regex.replace(r"\*\*", "##DOUBLESTAR##")
        regex = regex.replace(r"\*", "[^/]*")
        regex = regex.replace("##DOUBLESTAR##", ".*")
        regex = regex.replace(r"\?", "[^/]")

        # Permettre le match depuis n'importe quel sous-chemin si pas d'ancre
        if not glob.startswith("/"):
            regex = f"(^|.*/)({regex})(/.*)?$"
        else:
            regex = f"^{regex}(/.*)?$"

        try:
            return bool(re.match(regex, path, re.IGNORECASE))
        except re.error:
            return False

    def _is_notable(self, rel_path: str) -> bool:
        """Vrai si ce fichier mérite d'apparaître dans notable_files."""
        name = Path(rel_path).name.lower()
        notable_names = {
            "vmlinuz", "bzimage", "initramfs.img", "initrd",
            "modules.dep", "modules.dep.bin",
            "os-release", "fstab", "grub.cfg",
            "config.yaml",        # ZBM
            "snap.meta",          # snapshot fsdeploy
            "launch.sh",
        }
        notable_exts = {".sfs", ".squashfs", ".img", ".efi", ".EFI", ".zst"}
        notable_patterns = [
            r"^vmlinuz-",
            r"^initramfs-",
            r"^initrd",
            r"^kernel-",
            r"^bzImage",
            r"^modules-",
            r"^rootfs",
            r"^python-",
            r"\.meta$",
        ]
        if name in notable_names:
            return True
        if Path(rel_path).suffix in notable_exts:
            return True
        for pat in notable_patterns:
            if re.search(pat, name, re.IGNORECASE):
                return True
        return False

    def _extract_versions(self, notable_files: list[str]) -> dict[str, str]:
        """Extrait les numéros de version depuis les noms de fichiers notables."""
        versions: dict[str, str] = {}
        kver_re = re.compile(
            r"(?:vmlinuz|bzImage|initramfs|initrd|modules|kernel)[_-]"
            r"([\d]+\.[\d]+[\w.+-]*)"
        )
        pyver_re = re.compile(r"python([\d]+\.[\d]+)")

        for f in notable_files:
            name = Path(f).name
            m = kver_re.search(name)
            if m and "kernel" not in versions:
                versions["kernel"] = m.group(1)
            m = pyver_re.search(f)
            if m and "python" not in versions:
                versions["python"] = m.group(1)

        # Lire /lib/modules/* pour la version kernel
        if "kernel" not in versions:
            mod_base = self.mount_point / "lib" / "modules"
            if mod_base.is_dir():
                try:
                    subdirs = [d.name for d in mod_base.iterdir() if d.is_dir()]
                    if subdirs:
                        # Prendre la version la plus récente (tri sémantique approx)
                        versions["kernel"] = sorted(subdirs)[-1]
                except OSError:
                    pass

        return versions

    def _read_os_release(self) -> dict[str, str]:
        """Lit /etc/os-release ou /usr/lib/os-release si présent."""
        for candidate in [
            self.mount_point / "etc" / "os-release",
            self.mount_point / "usr" / "lib" / "os-release",
        ]:
            if candidate.is_file():
                info: dict[str, str] = {}
                try:
                    for line in candidate.read_text(errors="replace").splitlines():
                        line = line.strip()
                        if "=" in line and not line.startswith("#"):
                            k, _, v = line.partition("=")
                            info[k.strip()] = v.strip().strip('"')
                    return info
                except OSError:
                    pass
        return {}


# =============================================================================
# DÉTECTEUR PRINCIPAL
# =============================================================================

class DatasetDetector:
    """
    Analyse tous les datasets de tous les pools importés.
    Aucune hypothèse sur les noms — tout est déduit du contenu.

    Usage :
        detector = DatasetDetector(cfg)
        findings = detector.run(progress_cb=lambda msg: print(msg))
        # findings : list[DatasetFinding]
    """

    def __init__(self, cfg: FsDeployConfig) -> None:
        self.cfg = cfg
        self._lock = threading.Lock()

    def run(
        self,
        pools: list[str] | None = None,
        progress_cb=None,
        skip_empty: bool = True,
    ) -> list[DatasetFinding]:
        """
        Lance la détection complète.

        Args:
            pools:       liste de pools à analyser (None = tous les pools importés)
            progress_cb: callable(message: str) appelé pour chaque étape
            skip_empty:  ignorer les datasets vides (canmount=off ou used~=0)

        Returns:
            Liste de DatasetFinding triée par pool puis par dataset.
        """
        def log(msg: str) -> None:
            if progress_cb:
                progress_cb(msg)

        # ── 1. Lister tous les datasets ───────────────────────────────────────
        log("🔍 Listage de tous les datasets ZFS...")
        all_datasets = self._list_all_datasets(pools)
        log(f"   {len(all_datasets)} datasets trouvés")

        findings: list[DatasetFinding] = []

        # ── 2. Sonder chaque dataset ──────────────────────────────────────────
        for ds_props in all_datasets:
            ds_name = ds_props["name"]
            log(f"   ▶ {ds_name}  [{ds_props.get('used','?')}]")

            finding = DatasetFinding(
                dataset       = ds_name,
                pool          = ds_name.split("/")[0],
                mountpoint_zfs= ds_props.get("mountpoint", "none"),
                used          = ds_props.get("used", "?"),
                avail         = ds_props.get("avail", "?"),
                creation      = ds_props.get("creation", "?"),
            )

            # Ignorer si canmount=off et used très faible (juste métadonnées ZFS)
            if skip_empty and self._is_trivially_empty(ds_props):
                finding.roles = ["unknown"]
                finding.probe_error = "Ignoré (canmount=off ou dataset conteneur vide)"
                findings.append(finding)
                log(f"     ↳ ignoré (conteneur)")
                continue

            # ── Sonde du contenu ─────────────────────────────────────────────
            with DatasetProbe(ds_name, ds_props) as probe:
                if not probe._mounted and not probe._find_current_mount():
                    finding.probe_error = "Montage impossible"
                    finding.roles = ["unknown"]
                    log(f"     ↳ ❌ montage impossible")
                else:
                    roles, evidence, notable, versions, os_info, err = probe.probe()
                    finding.roles         = roles
                    finding.evidence      = evidence
                    finding.notable_files = notable
                    finding.versions      = versions
                    finding.os_info       = os_info
                    finding.probe_error   = err
                    finding.probe_mount   = str(probe.mount_point)
                    finding.confidence    = self._calc_confidence(roles, evidence)
                    finding.suggested_mount = self._suggest_mount(finding)

                    log(f"     ↳ rôles: {', '.join(roles)}  (conf={finding.confidence}%)")

            findings.append(finding)

        # ── 3. Post-traitement : affiner les rôles par contexte ───────────────
        findings = self._postprocess(findings)

        # ── 4. Sauvegarder dans la config ─────────────────────────────────────
        self._save_to_config(findings)

        return findings

    # ── Listing ZFS ───────────────────────────────────────────────────────────

    def _list_all_datasets(self, pools: list[str] | None) -> list[dict]:
        """
        Liste tous les datasets avec leurs propriétés clés.
        Retourne une liste de dicts.
        """
        cmd = [
            "zfs", "list",
            "-H",                        # no header, tab-separated
            "-o", "name,used,avail,mountpoint,canmount,type,creation",
            "-t", "filesystem",          # seulement les filesystems (pas volumes/snapshots)
            "-r",                        # récursif
        ]
        if pools:
            cmd.extend(pools)

        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        except subprocess.TimeoutExpired:
            return []

        if r.returncode != 0:
            return []

        result = []
        for line in r.stdout.strip().splitlines():
            parts = line.split("\t")
            if len(parts) < 6:
                continue
            result.append({
                "name":        parts[0],
                "used":        parts[1],
                "avail":       parts[2],
                "mountpoint":  parts[3],
                "canmount":    parts[4],
                "type":        parts[5],
                "creation":    parts[6] if len(parts) > 6 else "",
            })
        return result

    def _is_trivially_empty(self, props: dict) -> bool:
        """
        Vrai si le dataset est un pur conteneur sans données réelles.
        Un dataset avec canmount=off et less than 100K used est probablement juste
        un namespace ZFS (ex: pool/rootfs, pool/data, pool/archive…).
        """
        if props.get("canmount") not in ("off", "noauto"):
            return False
        # Parser la taille used (12K, 1.23M, etc.)
        used_str = props.get("used", "0")
        used_bytes = _parse_size(used_str)
        return used_bytes < 200 * 1024  # < 200 KB

    # ── Confiance et suggestions ──────────────────────────────────────────────

    def _calc_confidence(self, roles: list[str], evidence: dict) -> int:
        """Calcule un score de confiance 0-100."""
        if not roles or roles == ["unknown"]:
            return 0
        # Plus il y a de preuves concordantes, plus c'est fiable
        total_evidence = sum(len(v) for v in evidence.values())
        base = min(40 + total_evidence * 5, 100)
        # Bonus si un rôle conclusif a été trouvé
        conclusive_roles = {"efi", "kernel", "modules", "rootfs", "python_env"}
        if any(r in conclusive_roles for r in roles):
            base = min(base + 20, 100)
        return base

    def _suggest_mount(self, finding: DatasetFinding) -> str:
        """Suggère un point de montage logique selon le rôle détecté."""
        role = finding.primary_role
        ds   = finding.dataset
        name = ds.split("/")[-1]          # dernier composant du chemin ZFS

        suggestions = {
            "efi":           "/boot/efi",
            "boot":          "/boot",
            "kernel":        "/boot",
            "initramfs":     "/boot",
            "rootfs":        f"/mnt/{name}",
            "modules":       f"/mnt/{name}",
            "squashfs":      f"/mnt/{name}",
            "python_env":    "/mnt/python",
            "stream":        "/mnt/stream",
            "data":          f"/mnt/{name}",
            "overlay_upper": f"/mnt/upper/{name}",
            "snapshot_store":f"/mnt/snapshots/{name}",
        }
        return suggestions.get(role, f"/mnt/{name}")

    # ── Post-traitement ────────────────────────────────────────────────────────

    def _postprocess(self, findings: list[DatasetFinding]) -> list[DatasetFinding]:
        """
        Affine les rôles en tenant compte du contexte global.
        Ex : un dataset avec kernel ET initramfs ET presets/ → c'est le boot_pool.
        """
        for f in findings:
            # Dataset qui contient à la fois kernel, initramfs et presets → boot
            if {"kernel", "initramfs"}.issubset(set(f.roles)):
                if "boot" not in f.roles:
                    f.roles.insert(0, "boot")

            # Dataset rootfs avec python_env → probablement un rootfs complet avec TUI
            if "rootfs" in f.roles and "python_env" in f.roles:
                f.add_evidence("rootfs", "Rootfs complet avec environnement Python (TUI)")

            # Squashfs : affiner le sub_role depuis les preuves
            if "squashfs" in f.roles:
                self._refine_squashfs(f)

        # Trier : boot en premier, puis par pool, puis par nom
        role_order = ["boot", "efi", "kernel", "modules", "initramfs",
                      "squashfs", "rootfs", "python_env", "stream",
                      "overlay_upper", "snapshot_store", "data", "unknown"]

        def sort_key(f: DatasetFinding):
            try:
                return (role_order.index(f.primary_role), f.pool, f.dataset)
            except ValueError:
                return (99, f.pool, f.dataset)

        return sorted(findings, key=sort_key)

    def _refine_squashfs(self, finding: DatasetFinding) -> None:
        """Affine le sous-rôle d'un dataset squashfs selon les fichiers trouvés."""
        evidence_notes = " ".join(
            n for notes in finding.evidence.get("squashfs", []) for n in [notes]
        )
        if "rootfs" in evidence_notes or "rootfs" in finding.dataset.lower():
            finding.add_evidence("squashfs", "sous-rôle: rootfs")
        elif "modules" in evidence_notes or "modules" in finding.dataset.lower():
            finding.add_evidence("squashfs", "sous-rôle: modules")
        elif "python" in evidence_notes or "startup" in finding.dataset.lower():
            finding.add_evidence("squashfs", "sous-rôle: python")

    # ── Persistance ───────────────────────────────────────────────────────────

    def _save_to_config(self, findings: list[DatasetFinding]) -> None:
        """Sauvegarde le résumé de détection dans la config partagée."""
        import json
        from datetime import datetime, timezone

        summary = {
            "detected_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "total":        len(findings),
            "by_role":      {},
            "datasets":     [f.to_dict() for f in findings],
        }
        # Index par rôle
        for f in findings:
            for r in f.roles:
                summary["by_role"].setdefault(r, []).append(f.dataset)

        self.cfg.set("detection.status", "complete")
        self.cfg.set("detection.detected_at", summary["detected_at"])
        self.cfg.set("detection.report_json", json.dumps(summary))
        self.cfg.save()


# =============================================================================
# HELPERS
# =============================================================================

_SIZE_RE = re.compile(r"^([\d.]+)\s*([KMGTPE]?)$", re.IGNORECASE)
_SIZE_UNITS = {"": 1, "K": 1024, "M": 1024**2, "G": 1024**3,
               "T": 1024**4, "P": 1024**5, "E": 1024**6}

def _parse_size(s: str) -> int:
    """Convertit '12.3M' → bytes (int). Retourne 0 si invalide."""
    s = s.strip()
    m = _SIZE_RE.match(s)
    if not m:
        return 0
    try:
        value = float(m.group(1))
        unit  = m.group(2).upper()
        return int(value * _SIZE_UNITS.get(unit, 1))
    except (ValueError, KeyError):
        return 0
