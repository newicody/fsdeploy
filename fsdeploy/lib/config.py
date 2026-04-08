"""
fsdeploy.config
===============
Gestionnaire de configuration unique, partage entre :
  - le script de deploiement (Debian live)
  - le systeme une fois boote (initramfs / rootfs)

Base sur configobj + validation (configspec externe).
Un seul fichier INI sur disque, typiquement :
  /boot/fsdeploy/fsdeploy.conf     (dans boot_pool, persistant)
  /etc/fsdeploy/fsdeploy.conf      (systeme boote, symlink ou copie)

Usage :
    cfg = FsDeployConfig.default()
    cfg.set("pool.boot_pool", "boot_pool")
    cfg.set("kernel.active", "vmlinuz-6.12.0")
    cfg.save()

    pool = cfg.get("pool.boot_pool")
    cfg.section("stream")["youtube_key"]
"""

from __future__ import annotations

import grp
import os
import shutil
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from configobj import ConfigObj
    from validate import Validator
except ImportError as exc:
    raise ImportError("configobj manquant — pip install configobj") from exc


# ═════════════════════════════════════════════════════════════════
# CHEMINS
# ═════════════════════════════════════════════════════════════════

def _build_default_search() -> list[Path]:
    """
    Liste de chemins de recherche pour fsdeploy.conf.

    Priorite :
      1. $FSDEPLOY_INSTALL_DIR/fsdeploy.conf
      2. /boot/fsdeploy/fsdeploy.conf
      3. /mnt/zbm/boot/fsdeploy/fsdeploy.conf
      4. /mnt/boot/fsdeploy/fsdeploy.conf
      5. /etc/fsdeploy/fsdeploy.conf
      6. /tmp/fsdeploy/fsdeploy.conf  (fallback tests)
    """
    paths = []
    install_dir = os.environ.get("FSDEPLOY_INSTALL_DIR")
    if install_dir:
        paths.append(Path(install_dir) / "fsdeploy.conf")
    paths.extend([
        Path("/boot/fsdeploy/fsdeploy.conf"),
        Path("/mnt/zbm/boot/fsdeploy/fsdeploy.conf"),
        Path("/mnt/boot/fsdeploy/fsdeploy.conf"),
        Path("/etc/fsdeploy/fsdeploy.conf"),
        Path("/tmp/fsdeploy/fsdeploy.conf"),
    ])
    return paths


def _find_configspec() -> Path | None:
    """
    Cherche le fichier configspec.

    Ordre :
      1. A cote du module config.py (etc/fsdeploy.configspec)
      2. $FSDEPLOY_INSTALL_DIR/etc/fsdeploy.configspec
      3. /etc/fsdeploy/fsdeploy.configspec
    """
    # A cote de ce fichier
    here = Path(__file__).resolve().parent
    candidates = [
        here / "etc" / "fsdeploy.configspec",
        here.parent / "etc" / "fsdeploy.configspec",
    ]

    install_dir = os.environ.get("FSDEPLOY_INSTALL_DIR")
    if install_dir:
        candidates.insert(0, Path(install_dir) / "etc" / "fsdeploy.configspec")

    candidates.append(Path("/etc/fsdeploy/fsdeploy.configspec"))

    for p in candidates:
        if p.exists():
            return p
    return None


def _secure_config_file(path: Path) -> None:
    """
    Applique chmod 640 + chown :fsdeploy sur le fichier config.
    Silencieux si les permissions ne peuvent pas etre changees.
    """
    try:
        path.chmod(0o640)
    except OSError:
        pass

    try:
        fsdeploy_gid = grp.getgrnam("fsdeploy").gr_gid
        os.chown(str(path), -1, fsdeploy_gid)
    except (KeyError, OSError):
        pass


# ═════════════════════════════════════════════════════════════════
# CLASSE PRINCIPALE
# ═════════════════════════════════════════════════════════════════

class FsDeployConfig:
    """
    Gestionnaire de configuration fsdeploy (configobj).

    Thread-safe pour les operations de lecture. Les ecritures
    doivent etre protegees par l'appelant si multi-thread.
    """

    def __init__(self, path: Path | str, create: bool = True):
        self.path = Path(path)
        self._lock = threading.Lock()
        self._cfg: ConfigObj = None
        self._dirty = False
        self._load(create=create)

    # ── Factory ───────────────────────────────────────────────────

    @classmethod
    def default(cls, create: bool = True) -> "FsDeployConfig":
        """
        Charge la config depuis le premier emplacement trouve.
        Cree le fichier si create=True et aucun n'existe.
        """
        search = _build_default_search()

        for p in search:
            if p.exists():
                return cls(p, create=False)

        if not create:
            raise FileNotFoundError(
                "Aucun fichier fsdeploy.conf trouve.")

        for p in search:
            try:
                p.parent.mkdir(parents=True, exist_ok=True)
                return cls(p, create=True)
            except OSError:
                continue

        raise OSError("Impossible de creer fsdeploy.conf.")

    @classmethod
    def at(cls, path: Path | str) -> "FsDeployConfig":
        return cls(path, create=True)

    # ── Chargement ────────────────────────────────────────────────

    def _load(self, *, create: bool) -> None:
        """Charge le fichier avec validation configspec."""
        # Charger le configspec
        spec_path = _find_configspec()
        if spec_path:
            spec = ConfigObj(str(spec_path), list_values=False,
                             encoding="utf-8")
        else:
            spec = None

        if not self.path.exists():
            if not create:
                raise FileNotFoundError(f"Config introuvable : {self.path}")
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._cfg = ConfigObj(
                configspec=spec, encoding="utf-8",
                indent_type="    ", write_empty_values=True,
            )
            self._cfg.filename = str(self.path)
            self._apply_defaults()
            self._set_meta("created")
            self._cfg.write()
            _secure_config_file(self.path)
        else:
            self._cfg = ConfigObj(
                str(self.path), configspec=spec, encoding="utf-8",
                indent_type="    ", write_empty_values=True,
            )
            self._apply_defaults()

        self._dirty = False

    def _apply_defaults(self) -> None:
        """Applique le configspec (valeurs par defaut pour les cles manquantes)."""
        if self._cfg.configspec:
            v = Validator()
            self._cfg.validate(v, preserve_errors=True, copy=True)

    def _set_meta(self, action: str) -> None:
        """Met a jour les metadonnees."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if "meta" not in self._cfg:
            self._cfg["meta"] = {}
        self._cfg["meta"]["last_saved"] = now
        self._cfg["meta"]["last_saved_by"] = os.environ.get("USER", "unknown")
        if action == "created":
            self._cfg["meta"]["created_at"] = now

    # ── Acces aux valeurs ─────────────────────────────────────────

    def get(self, key: str, default: Any = None) -> Any:
        """
        Lit par cle pointee : "section.cle" ou "section.sub.cle".
        """
        parts = key.split(".")
        node = self._cfg
        try:
            for part in parts:
                node = node[part]
            return node
        except (KeyError, TypeError):
            return default

    def set(self, key: str, value: Any) -> None:
        """
        Ecrit par cle pointee. Cree les sous-sections manquantes.
        """
        parts = key.split(".")
        node = self._cfg
        for part in parts[:-1]:
            if part not in node or not isinstance(node[part], dict):
                node[part] = {}
            node = node[part]
        node[parts[-1]] = value
        self._dirty = True

    def section(self, name: str) -> dict:
        """Acces direct a une section."""
        return self._cfg.get(name, {})

    def has(self, key: str) -> bool:
        return self.get(key) is not None

    # ── Presets ───────────────────────────────────────────────────

    def preset(self, name: str) -> dict:
        """Retourne un preset par nom."""
        presets = self._cfg.get("presets", {})
        p = presets.get(name, {})
        return dict(p) if isinstance(p, dict) else {}

    def active_preset(self) -> dict:
        """Retourne le preset actif."""
        name = self.get("presets.active", "")
        return self.preset(name) if name else {}

    # ── Persistance ───────────────────────────────────────────────

    def save(self) -> None:
        """Ecrit sur disque."""
        self._set_meta("saved")
        self._cfg.write()
        _secure_config_file(self.path)
        self._dirty = False

    def reload(self) -> None:
        """Recharge depuis le disque."""
        self._load(create=False)

    @property
    def dirty(self) -> bool:
        return self._dirty

    # ── Validation ────────────────────────────────────────────────

    def validate(self) -> dict:
        """
        Valide la config contre le configspec.
        Retourne un dict d'erreurs (vide = tout OK).
        """
        if not self._cfg.configspec:
            return {}

        v = Validator()
        result = self._cfg.validate(v, preserve_errors=True)
        errors = {}

        def collect(res, prefix=""):
            if isinstance(res, dict):
                for k, val in res.items():
                    collect(val, f"{prefix}{k}.")
            elif res is not True:
                errors[prefix.rstrip(".")] = str(res)

        collect(result)
        return errors

    # ── Representation ────────────────────────────────────────────

    def __repr__(self) -> str:
        return f"FsDeployConfig({self.path})"

    def dump(self) -> str:
        """Dump textuel complet pour debug."""
        lines = [f"# FsDeployConfig: {self.path}"]
        for section_name in self._cfg:
            section = self._cfg[section_name]
            if isinstance(section, dict):
                lines.append(f"[{section_name}]")
                for k, v in section.items():
                    if isinstance(v, dict):
                        lines.append(f"  [[{k}]]")
                        for kk, vv in v.items():
                            lines.append(f"    {kk} = {vv}")
                    else:
                        lines.append(f"  {k} = {v}")
            else:
                lines.append(f"{section_name} = {section}")
        return "\n".join(lines)
