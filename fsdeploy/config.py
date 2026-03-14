"""
fsdeploy.config
===============
Gestionnaire de configuration unique, partagé entre :
  - le script de déploiement (Debian live)
  - le système une fois booté (initramfs / rootfs)

Basé sur configobj + validation (configspec).
Un seul fichier INI sur disque, typiquement :
  /boot/fsdeploy/fsdeploy.conf     (dans boot_pool, persistant)
  /etc/fsdeploy/fsdeploy.conf      (système booté, symlink ou copie)

Principe :
  • Toute classe qui a besoin de lire/écrire la config crée une instance
    FsDeployConfig(path) ou utilise FsDeployConfig.default().
  • Les sections sont des attributs du même nom que la section INI.
  • get() / set() / save() / reload() sont les seules opérations nécessaires.
  • Les modifications sont journalisées (qui a modifié quoi).

Usage minimal :
    cfg = FsDeployConfig.default()
    cfg.set("pool.boot_pool", "boot_pool")
    cfg.set("kernel.active", "vmlinuz-6.6.47-gentoo")
    cfg.save()

    pool = cfg.get("pool.boot_pool")          # "boot_pool"
    cfg.section("stream")["youtube_key"]      # accès section directe
"""

from __future__ import annotations

import grp
import os
import shutil
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

# configobj >= 5.0.8
try:
    from configobj import ConfigObj, ConfigspecError
    from validate import Validator
except ImportError as exc:
    raise ImportError(
        "configobj manquant — pip install configobj"
    ) from exc


# =============================================================================
# CHEMINS PAR DÉFAUT
# =============================================================================

def _build_default_search() -> list[Path]:
    """
    Construit la liste de chemins de recherche pour fsdeploy.conf.

    Priorité :
      1. $FSDEPLOY_INSTALL_DIR/fsdeploy.conf  (posé par launch.sh dans .env)
      2. /boot/fsdeploy/fsdeploy.conf          (dans boot_pool, persistant)
      3. /mnt/zbm/boot/fsdeploy/fsdeploy.conf  (boot_pool monté sous /mnt/zbm)
      4. /mnt/boot/fsdeploy/fsdeploy.conf      (boot_pool monté sous /mnt/boot)
      5. /etc/fsdeploy/fsdeploy.conf           (système installé)
      6. /tmp/fsdeploy/fsdeploy.conf           (fallback tests / live sans ZFS)
    """
    candidates: list[Path] = []

    # Variable posée par launch.sh via le fichier .env sourcé par le wrapper
    install_dir = os.environ.get("FSDEPLOY_INSTALL_DIR", "").strip()
    if install_dir:
        candidates.append(Path(install_dir) / "fsdeploy.conf")

    candidates += [
        Path("/boot/fsdeploy/fsdeploy.conf"),
        Path("/mnt/zbm/boot/fsdeploy/fsdeploy.conf"),
        Path("/mnt/boot/fsdeploy/fsdeploy.conf"),
        Path("/etc/fsdeploy/fsdeploy.conf"),
        Path("/tmp/fsdeploy/fsdeploy.conf"),
    ]

    return candidates


_DEFAULT_SEARCH: list[Path] = _build_default_search()


# =============================================================================
# CONFIGSPEC — schéma de validation + valeurs par défaut
# =============================================================================

CONFIGSPEC = """
# ── Environnement ────────────────────────────────────────────────────────────
[env]
mode            = option(deploy, booted, initramfs, default=deploy)
created_at      = string(default="")
last_modified   = string(default="")
last_modified_by = string(default="")
fsdeploy_version = string(default="0.1.0")

# ── Pools ZFS ────────────────────────────────────────────────────────────────
[pool]
boot_pool       = string(default="boot_pool")
fast_pool       = string(default="fast_pool")
data_pool       = string(default="data_pool")
# Chemin de montage effectif de boot_pool (détecté au runtime)
boot_mount      = string(default="")

# ── Partitions ───────────────────────────────────────────────────────────────
[partition]
# Rempli par le moteur de détection
efi_device      = string(default="")
efi_mount       = string(default="")
# Liste des disques détectés, séparés par des virgules
disks           = list(default=list())

# ── Détection des datasets ────────────────────────────────────────────────────
[detection]
# État global de la détection (none | partial | complete)
status          = option(none, partial, complete, default=none)
# Rapport JSON de la dernière détection (chemin fichier)
report_path     = string(default="")
# Timestamp ISO de la dernière détection
last_run        = string(default="")

# ── Montages ─────────────────────────────────────────────────────────────────
[mounts]
# Point de montage racine des datasets pendant le déploiement
deploy_root     = string(default="/mnt/deploy")
# Montages supplémentaires (liste de "dataset:point_de_montage")
extra           = list(default=list())

# ── Noyau ────────────────────────────────────────────────────────────────────
[kernel]
# Noyau actif (symlink vmlinuz → ce fichier)
active          = string(default="")
# Répertoire source des noyaux trouvés
source_dir      = string(default="")
# Version noyau actif
version         = string(default="")

# ── Initramfs ────────────────────────────────────────────────────────────────
[initramfs]
# Type : zbm | minimal | stream
type            = option(zbm, minimal, stream, default=zbm)
# Chemin de l'initramfs actif
active          = string(default="")
# Options dracut supplémentaires
dracut_opts     = string(default="")
# Modules à inclure (liste)
modules         = list(default=list())

# ── ZFSBootMenu ──────────────────────────────────────────────────────────────
[zbm]
# Version ZBM installée
version         = string(default="")
# Chemin de l'EFI ZBM installé
efi_path        = string(default="")
# Options de la cmdline ZBM
cmdline         = string(default="")
# Timeout ZBM (secondes)
timeout         = integer(min=0, max=60, default=3)
# Dataset racine que ZBM doit présenter
bootfs          = string(default="")

# ── Presets de boot ──────────────────────────────────────────────────────────
[presets]
# Preset actif (nom de section dans [[presets.entries]])
active          = string(default="")
# Les presets eux-mêmes sont dans des sous-sections dynamiques

# ── Stream YouTube ───────────────────────────────────────────────────────────
[stream]
enabled         = boolean(default=False)
youtube_key     = string(default="")
resolution      = string(default="1920x1080")
fps             = integer(min=1, max=60, default=30)
bitrate         = string(default="4500k")
audio_bitrate   = string(default="128k")
# Délai avant démarrage du stream après boot (secondes)
start_delay     = integer(min=0, max=300, default=30)
# Chemin du module python de stream embarqué dans l'initramfs
stream_module   = string(default="")

# ── Snapshots ────────────────────────────────────────────────────────────────
[snapshots]
base_dir        = string(default="")
retention_days  = integer(min=1, max=365, default=30)
compress        = boolean(default=True)

# ── Logging ──────────────────────────────────────────────────────────────────
[log]
level           = option(debug, info, warning, error, default=info)
dir             = string(default="")
max_size_mb     = integer(min=1, max=500, default=50)
""".strip()


# =============================================================================
# HELPERS INTERNES
# =============================================================================

def _secure_config_file(path: Path) -> None:
    """
    Applique sur le fichier de config :
      - chmod 640  (propriétaire rw, groupe r, autres rien)
      - chown :fsdeploy  (groupe fsdeploy si disponible, sinon groupe courant)

    Le fichier peut contenir des clés sensibles (youtube_key, etc.).
    Silencieux si le groupe fsdeploy est absent ou si les droits manquent.
    """
    try:
        path.chmod(0o640)
    except OSError:
        pass

    try:
        gid = grp.getgrnam("fsdeploy").gr_gid
        os.chown(path, os.getuid(), gid)
    except (KeyError, PermissionError, OSError):
        # Groupe fsdeploy absent ou chown impossible → pas bloquant
        pass


def _detect_caller() -> str:
    """Identifie le module appelant pour la métadonnée last_modified_by."""
    import inspect
    frame = inspect.currentframe()
    try:
        # Remonter la pile jusqu'à trouver un appelant hors de config.py
        for _ in range(10):
            if frame is None:
                break
            frame = frame.f_back
            if frame is None:
                break
            module = frame.f_globals.get("__name__", "")
            if module and module != __name__:
                return module
    finally:
        del frame
    return "unknown"


# =============================================================================
# CLASSE PRINCIPALE
# =============================================================================

class FsDeployConfig:
    """
    Gestionnaire de configuration fsdeploy (configobj).

    Attributs publics :
        path (Path)        — chemin du fichier .conf sur disque
        cfg  (ConfigObj)   — objet configobj sous-jacent (accès direct possible)

    Méthodes principales :
        get(key)                → valeur  (key = "section.clé" ou "section.sub.clé")
        set(key, value)         → None    (marque dirty)
        section(name)           → dict-like (sous-section configobj)
        save()                  → None    (écrit sur disque si dirty)
        reload()                → None    (relit le fichier)
        validate()              → (bool, dict)  (True + {} si OK)
        as_dict()               → dict    (copie complète)
        preset(name)            → dict | None
        set_preset(name, data)  → None
        delete_preset(name)     → None
        list_presets()          → list[str]
    """

    _lock = threading.Lock()

    # ── Construction ─────────────────────────────────────────────────────────

    def __init__(self, path: Path | str, *, create: bool = True) -> None:
        self.path = Path(path)
        self._dirty = False
        self._cfg: ConfigObj | None = None
        self._load(create=create)

    @classmethod
    def default(cls, *, create: bool = True) -> "FsDeployConfig":
        """
        Retourne une instance en cherchant le fichier dans les emplacements
        par défaut.  Crée le fichier dans le premier emplacement accessible
        si aucun n'existe et create=True.

        L'ordre de recherche tient compte de $FSDEPLOY_INSTALL_DIR posé par
        launch.sh dans le fichier .env sourcé par le wrapper global.
        """
        # Reconstruire la liste à chaque appel pour honorer les variables
        # d'environnement éventuellement chargées après l'import du module.
        search = _build_default_search()

        for p in search:
            if p.exists():
                return cls(p, create=False)

        if not create:
            raise FileNotFoundError(
                "Aucun fichier fsdeploy.conf trouvé dans les emplacements par défaut."
            )

        # Créer dans le premier emplacement dont le répertoire parent est accessible
        for p in search:
            try:
                p.parent.mkdir(parents=True, exist_ok=True)
                return cls(p, create=True)
            except OSError:
                continue

        raise OSError("Impossible de créer fsdeploy.conf — aucun emplacement accessible.")

    @classmethod
    def at(cls, path: Path | str) -> "FsDeployConfig":
        """Raccourci : instance à un chemin précis, crée si besoin."""
        return cls(path, create=True)

    # ── Chargement interne ────────────────────────────────────────────────────

    def _load(self, *, create: bool) -> None:
        spec = ConfigObj(
            CONFIGSPEC.splitlines(),
            list_values=False,
            encoding="utf-8",
        )

        if not self.path.exists():
            if not create:
                raise FileNotFoundError(f"Config introuvable : {self.path}")
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._cfg = ConfigObj(
                configspec=spec,
                encoding="utf-8",
                indent_type="    ",
                write_empty_values=True,
            )
            self._cfg.filename = str(self.path)
            self._apply_defaults()
            self._set_meta("created")
            self._cfg.write()
            # Permissions sécurisées dès la création (youtube_key, etc.)
            _secure_config_file(self.path)
        else:
            self._cfg = ConfigObj(
                str(self.path),
                configspec=spec,
                encoding="utf-8",
                indent_type="    ",
                write_empty_values=True,
            )
            # Appliquer les valeurs par défaut pour les clés manquantes
            self._apply_defaults()

        self._dirty = False

    def _apply_defaults(self) -> None:
        """Applique le configspec (valeurs par défaut) sans validation stricte."""
        v = Validator()
        self._cfg.validate(v, preserve_errors=True, copy=True)  # copy=True → remplit les manquantes

    # ── Accès aux valeurs ─────────────────────────────────────────────────────

    def get(self, key: str, default: Any = None) -> Any:
        """
        Lit une valeur par clé pointée : "section.clé" ou "section.sub.clé".
        Retourne default si introuvable.
        """
        parts = key.split(".")
        node: Any = self._cfg
        try:
            for part in parts:
                node = node[part]
            return node
        except (KeyError, TypeError):
            return default

    def set(self, key: str, value: Any) -> None:
        """
        Écrit une valeur par clé pointée : "section.clé".
        Crée les sous-sections manquantes.
        Marque la config comme modifiée (dirty).
        """
        parts = key.split(".")
        node = self._cfg
        for part in parts[:-1]:
            if part not in node:
                node[part] = {}
            node = node[part]
        node[parts[-1]] = value
        self._dirty = True

    def section(self, name: str) -> Any:
        """
        Retourne une sous-section configobj.
        Crée la section si elle n'existe pas.
        Accès direct : cfg.section("stream")["youtube_key"]
        """
        if name not in self._cfg:
            self._cfg[name] = {}
            self._dirty = True
        return self._cfg[name]

    def __getitem__(self, key: str) -> Any:
        """Accès dict : cfg["pool.boot_pool"] ou cfg["pool"]."""
        return self.get(key)

    def __setitem__(self, key: str, value: Any) -> None:
        self.set(key, value)

    # ── Presets ──────────────────────────────────────────────────────────────

    def preset(self, name: str) -> dict | None:
        """Retourne un preset par son nom (sous-section de [presets])."""
        try:
            return dict(self._cfg["presets"][name])
        except KeyError:
            return None

    def set_preset(self, name: str, data: dict) -> None:
        """Crée ou met à jour un preset."""
        if "presets" not in self._cfg:
            self._cfg["presets"] = {}
        self._cfg["presets"][name] = data
        self._dirty = True

    def delete_preset(self, name: str) -> None:
        """Supprime un preset."""
        try:
            del self._cfg["presets"][name]
            self._dirty = True
        except KeyError:
            pass

    def list_presets(self) -> list[str]:
        """Retourne la liste des noms de presets."""
        try:
            # Exclure les clés scalaires (active, etc.)
            return [
                k for k, v in self._cfg.get("presets", {}).items()
                if isinstance(v, dict)
            ]
        except (AttributeError, TypeError):
            return []

    # ── Persistance ──────────────────────────────────────────────────────────

    def save(self, *, force: bool = False) -> bool:
        """
        Sauvegarde sur disque si dirty (ou force=True).
        Crée une sauvegarde .bak avant d'écraser.
        Réapplique les permissions sécurisées après écriture.
        Retourne True si l'écriture a eu lieu.
        """
        if not self._dirty and not force:
            return False

        with self._lock:
            self._set_meta("modified")

            # Sauvegarde .bak si le fichier existe déjà
            if self.path.exists():
                bak = self.path.with_suffix(".conf.bak")
                shutil.copy2(str(self.path), str(bak))

            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._cfg.filename = str(self.path)
            self._cfg.write()
            _secure_config_file(self.path)
            self._dirty = False
            return True

    def reload(self) -> None:
        """Relit le fichier depuis le disque (écrase les modifications non sauvées)."""
        self._load(create=False)

    # ── Validation ───────────────────────────────────────────────────────────

    def validate(self) -> tuple[bool, dict]:
        """
        Valide la config contre le configspec.
        Retourne (True, {}) si tout est OK,
                 (False, {section.key: erreur, ...}) sinon.
        """
        v = Validator()
        result = self._cfg.validate(v, preserve_errors=True)

        if result is True:
            return True, {}

        errors: dict[str, str] = {}
        if isinstance(result, dict):
            self._flatten_errors(result, errors)
        return False, errors

    def _flatten_errors(
        self, node: dict, out: dict, prefix: str = ""
    ) -> None:
        for k, v in node.items():
            full_key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                self._flatten_errors(v, out, full_key)
            elif v is not True:
                out[full_key] = str(v) if v is not False else "valeur manquante"

    # ── Export ────────────────────────────────────────────────────────────────

    def as_dict(self) -> dict:
        """Retourne une copie profonde de toute la configuration sous forme de dict."""
        return self._cfg.dict()

    def as_ini_string(self) -> str:
        """Retourne la config complète au format INI (pour affichage / debug)."""
        lines: list[str] = []
        self._cfg.filename = None  # évite d'écrire sur disque
        lines = self._cfg.write()
        self._cfg.filename = str(self.path)
        return "\n".join(lines)

    # ── Métadonnées internes ──────────────────────────────────────────────────

    def _set_meta(self, event: str) -> None:
        now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        caller = _detect_caller()
        if event == "created":
            self._cfg.setdefault("env", {})
            self._cfg["env"]["created_at"] = now
        self._cfg.setdefault("env", {})
        self._cfg["env"]["last_modified"] = now
        self._cfg["env"]["last_modified_by"] = caller

    # ── Représentation ────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        dirty = " [dirty]" if self._dirty else ""
        return f"<FsDeployConfig path={self.path}{dirty}>"

    def __str__(self) -> str:
        return self.as_ini_string()

    # ── Propriétés raccourcis ──────────────────────────────────────────────────

    @property
    def boot_mount(self) -> Path:
        """Point de montage effectif de boot_pool."""
        mp = self.get("pool.boot_mount", "")
        return Path(mp) if mp else Path("/boot")

    @boot_mount.setter
    def boot_mount(self, value: Path | str) -> None:
        self.set("pool.boot_mount", str(value))

    @property
    def is_deploy_mode(self) -> bool:
        return self.get("env.mode", "deploy") == "deploy"

    @property
    def is_booted_mode(self) -> bool:
        return self.get("env.mode", "deploy") == "booted"

    @property
    def stream_enabled(self) -> bool:
        v = self.get("stream.enabled", False)
        if isinstance(v, str):
            return v.lower() in ("true", "1", "yes")
        return bool(v)

    @stream_enabled.setter
    def stream_enabled(self, value: bool) -> None:
        self.set("stream.enabled", value)
