"""
fsdeploy.core.cli
==================
Résolution des arguments en ligne de commande vs configobj.

Règle absolue : CLI > configobj > valeur par défaut.

Chaque classe opérationnelle déclare ses propres options via :
  - un classmethod `cli_args(parser)` qui ajoute les arguments argparse
  - un classmethod `from_cli(args, cfg)` qui construit l'instance

Le mixin `CliMixin` fournit l'infrastructure commune.
`GlobalArgs` porte les options présentes dans TOUTES les classes
  (bypass, verbose, debug, dry-run, log-level).

Utilisable indépendamment :
    parser = argparse.ArgumentParser()
    GlobalArgs.add(parser)
    PoolDetectorArgs.add(parser)
    args = parser.parse_args()
    cfg  = FsDeployConfig.default()
    opts = PoolDetectorArgs.resolve(args, cfg)
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, Type, TypeVar

T = TypeVar("T")


# =============================================================================
# RÉSOLVEUR CLI > CONFIGOBJ
# =============================================================================

class CliResolver:
    """
    Fusionne args (argparse.Namespace) et cfg (FsDeployConfig).
    La valeur CLI gagne toujours sur la valeur config.

    Logique :
        1. Si l'argument CLI est présent et différent de sa valeur par défaut
           → utiliser CLI
        2. Sinon → utiliser configobj
        3. Sinon → utiliser la valeur par défaut déclarée dans la dataclass
    """

    def __init__(
        self,
        args: argparse.Namespace | None,
        cfg: Any | None,   # FsDeployConfig
        *,
        cli_defaults: dict[str, Any] = None,
    ) -> None:
        self._args     = args
        self._cfg      = cfg
        self._defaults = cli_defaults or {}

    def get(
        self,
        cli_key: str,
        cfg_key: str,
        default: Any = None,
        *,
        cast: type | None = None,
    ) -> Any:
        """
        Résout une valeur en suivant la priorité CLI > configobj > default.

        Args:
            cli_key:  nom de l'attribut dans argparse.Namespace (ex: "boot_pool")
            cfg_key:  chemin configobj pointé (ex: "pool.boot_pool")
            default:  valeur par défaut si rien n'est défini
            cast:     conversion de type si nécessaire (ex: int, Path, bool)
        """
        # ── 1. Valeur CLI ─────────────────────────────────────────────────
        cli_val = None
        if self._args is not None and hasattr(self._args, cli_key):
            cli_val = getattr(self._args, cli_key)

        # Comparer à la valeur par défaut argparse pour détecter si l'arg
        # a vraiment été fourni par l'utilisateur
        cli_default = self._defaults.get(cli_key)
        cli_was_set = cli_val is not None and cli_val != cli_default

        if cli_was_set:
            return self._cast(cli_val, cast)

        # ── 2. Valeur configobj ────────────────────────────────────────────
        if self._cfg is not None:
            cfg_val = self._cfg.get(cfg_key)
            if cfg_val not in (None, "", [], {}):
                return self._cast(cfg_val, cast)

        # ── 3. Valeur par défaut ───────────────────────────────────────────
        return self._cast(default, cast) if default is not None else default

    def get_bool(self, cli_key: str, cfg_key: str, default: bool = False) -> bool:
        """Résolution spécialisée pour les booléens (flags CLI)."""
        # Flag CLI présent → True immédiatement
        if self._args is not None and hasattr(self._args, cli_key):
            cli_val = getattr(self._args, cli_key)
            if isinstance(cli_val, bool) and cli_val:
                return True

        # Config
        if self._cfg is not None:
            cfg_val = self._cfg.get(cfg_key)
            if cfg_val is not None:
                if isinstance(cfg_val, bool):
                    return cfg_val
                if isinstance(cfg_val, str):
                    return cfg_val.lower() in ("true", "1", "yes", "on")

        return default

    @staticmethod
    def _cast(val: Any, cast: type | None) -> Any:
        if cast is None or val is None:
            return val
        try:
            if cast is bool:
                if isinstance(val, bool):
                    return val
                return str(val).lower() in ("true", "1", "yes", "on")
            if cast is Path:
                return Path(val)
            return cast(val)
        except (ValueError, TypeError):
            return val


# =============================================================================
# ARGUMENTS GLOBAUX (présents dans toutes les classes)
# =============================================================================

@dataclass
class GlobalOptions:
    """Options communes à toutes les opérations fsdeploy."""

    # Mode d'exécution
    verbose:   bool = False    # affiche les commandes exécutées
    debug:     bool = False    # dump complet (config, état, traces)
    dry_run:   bool = False    # simule sans rien faire
    quiet:     bool = False    # supprime toute sortie non critique

    # Sécurité
    bypass:    bool = False    # désactive toutes les vérifications de sécurité

    # Config
    config:    str  = ""       # chemin vers fsdeploy.conf (surcharge le défaut)

    # Log
    log_level: str  = "info"   # debug | info | warning | error

    @classmethod
    def add_to_parser(cls, parser: argparse.ArgumentParser) -> None:
        """Ajoute les arguments globaux à n'importe quel parser."""
        g = parser.add_argument_group("options globales")
        g.add_argument(
            "-v", "--verbose",
            action="store_true", default=False,
            help="Affiche toutes les commandes exécutées et leurs sorties",
        )
        g.add_argument(
            "--debug",
            action="store_true", default=False,
            help="Mode debug : dump complet de la config et des états internes",
        )
        g.add_argument(
            "-n", "--dry-run",
            dest="dry_run",
            action="store_true", default=False,
            help="Simule les opérations sans rien modifier",
        )
        g.add_argument(
            "-q", "--quiet",
            action="store_true", default=False,
            help="Mode silencieux (erreurs uniquement)",
        )
        g.add_argument(
            "--bypass",
            action="store_true", default=False,
            help="⚠ Désactive toutes les vérifications de sécurité",
        )
        g.add_argument(
            "-c", "--config",
            metavar="FICHIER",
            default="",
            help="Chemin vers fsdeploy.conf (défaut : auto-détection)",
        )
        g.add_argument(
            "--log-level",
            dest="log_level",
            choices=["debug", "info", "warning", "error"],
            default="info",
            help="Niveau de log (défaut: info)",
        )

    @classmethod
    def from_args(cls, args: argparse.Namespace, cfg: Any = None) -> "GlobalOptions":
        r = CliResolver(args, cfg, cli_defaults={
            "verbose": False, "debug": False, "dry_run": False,
            "quiet": False, "bypass": False, "config": "", "log_level": "info",
        })
        return cls(
            verbose   = r.get_bool("verbose",   "env.verbose",   False),
            debug     = r.get_bool("debug",     "env.debug",     False),
            dry_run   = r.get_bool("dry_run",   "env.dry_run",   False),
            quiet     = r.get_bool("quiet",     "env.quiet",     False),
            bypass    = r.get_bool("bypass",    "env.bypass",    False),
            config    = r.get("config",         "env.config",    ""),
            log_level = r.get("log_level",      "log.level",     "info"),
        )


# =============================================================================
# MIXIN CLI
# =============================================================================

class CliMixin:
    """
    Mixin à hériter pour rendre une classe configurable via CLI + configobj.

    Chaque classe fille doit implémenter :
        - cli_args(parser)       : ajoute ses propres arguments
        - from_cli(args, cfg)    : construit l'instance depuis CLI + config

    Usage :
        class PoolDetector(CliMixin):
            @classmethod
            def cli_args(cls, parser):
                GlobalOptions.add_to_parser(parser)
                g = parser.add_argument_group("détection pools")
                g.add_argument("--pool", nargs="+", ...)

            @classmethod
            def from_cli(cls, args, cfg):
                r = CliResolver(args, cfg)
                return cls(cfg, pools=r.get("pool", "detection.pools", []))

        # Standalone :
        parser = argparse.ArgumentParser()
        PoolDetector.cli_args(parser)
        args = parser.parse_args()
        d = PoolDetector.from_cli(args, None)
    """

    # Chaque sous-classe remplace ceci
    _CLI_DESCRIPTION: str = ""

    @classmethod
    def make_parser(cls) -> argparse.ArgumentParser:
        """Crée un parser complet (global + spécifique à la classe)."""
        parser = argparse.ArgumentParser(
            description      = cls._CLI_DESCRIPTION or cls.__doc__ or "",
            formatter_class  = argparse.RawDescriptionHelpFormatter,
            allow_abbrev     = False,
        )
        GlobalOptions.add_to_parser(parser)
        cls.cli_args(parser)
        return parser

    @classmethod
    def cli_args(cls, parser: argparse.ArgumentParser) -> None:
        """Surcharger pour ajouter les arguments spécifiques à la classe."""
        pass

    @classmethod
    def from_cli(cls, args: argparse.Namespace, cfg: Any) -> "CliMixin":
        """Surcharger pour construire l'instance depuis CLI + config."""
        raise NotImplementedError(f"{cls.__name__}.from_cli() non implémenté")

    @classmethod
    def run_standalone(cls, argv: list[str] | None = None) -> int:
        """
        Point d'entrée pour utiliser la classe directement en ligne de commande.
        Retourne le code de sortie.

        Usage :
            if __name__ == "__main__":
                sys.exit(PoolDetector.run_standalone())
        """
        parser = cls.make_parser()
        args   = parser.parse_args(argv)

        # Charger la config si précisée
        cfg = None
        try:
            from fsdeploy.config import FsDeployConfig
            cfg_path = getattr(args, "config", "") or ""
            if cfg_path:
                cfg = FsDeployConfig(cfg_path)
            else:
                cfg = FsDeployConfig.default(create=False)
        except Exception:
            pass  # pas de config → CLI only

        try:
            instance = cls.from_cli(args, cfg)
            return instance._cli_main(args) or 0
        except KeyboardInterrupt:
            print("\nInterrompu.")
            return 130
        except Exception as e:
            if getattr(args, "debug", False):
                import traceback
                traceback.print_exc()
            else:
                print(f"Erreur : {e}", file=sys.stderr)
            return 1

    def _cli_main(self, args: argparse.Namespace) -> int:
        """Surcharger pour implémenter le comportement CLI principal."""
        return 0


# =============================================================================
# OPTIONS PAR CLASSE — dataclasses des paramètres résolus
# Chacune correspond à un fichier core/ ou boot/
# =============================================================================

@dataclass
class PoolDetectorOptions:
    """Options pour core/detection/pool.py"""
    pools:          list[str] = field(default_factory=list)
    import_missing: bool      = False
    readonly:       bool      = True
    no_import:      bool      = False   # lister sans importer

    @classmethod
    def add_to_parser(cls, parser: argparse.ArgumentParser) -> None:
        g = parser.add_argument_group("détection pools")
        g.add_argument(
            "--pool", nargs="+", metavar="NOM",
            dest="pools", default=[],
            help="Pools à analyser (défaut : tous les pools importés)",
        )
        g.add_argument(
            "--import-missing",
            action="store_true", default=False,
            help="Tenter d'importer les pools non encore importés",
        )
        g.add_argument(
            "--readonly",
            action="store_true", default=True,
            help="Importer en lecture seule (défaut : activé)",
        )
        g.add_argument(
            "--no-import",
            dest="no_import",
            action="store_true", default=False,
            help="Lister les pools sans les importer",
        )

    @classmethod
    def resolve(cls, args: argparse.Namespace, cfg: Any) -> "PoolDetectorOptions":
        r = CliResolver(args, cfg)
        return cls(
            pools          = r.get("pools",          "detection.pools",  []),
            import_missing = r.get_bool("import_missing", "detection.import_missing", False),
            readonly       = r.get_bool("readonly",       "detection.readonly",       True),
            no_import      = r.get_bool("no_import",      "detection.no_import",      False),
        )


@dataclass
class DatasetDetectorOptions:
    """Options pour core/detection/dataset.py"""
    pools:        list[str] = field(default_factory=list)
    skip_empty:   bool      = True
    max_depth:    int       = 6
    max_files:    int       = 2000

    @classmethod
    def add_to_parser(cls, parser: argparse.ArgumentParser) -> None:
        g = parser.add_argument_group("détection datasets")
        g.add_argument(
            "--pool", nargs="+", metavar="NOM",
            dest="pools", default=[],
            help="Limiter la détection à ces pools",
        )
        g.add_argument(
            "--no-skip-empty",
            dest="skip_empty",
            action="store_false", default=True,
            help="Analyser aussi les datasets vides (conteneurs)",
        )
        g.add_argument(
            "--max-depth", metavar="N",
            type=int, default=6,
            help="Profondeur max de scan du contenu (défaut: 6)",
        )
        g.add_argument(
            "--max-files", metavar="N",
            type=int, default=2000,
            help="Nombre max de fichiers scannés par dataset (défaut: 2000)",
        )

    @classmethod
    def resolve(cls, args: argparse.Namespace, cfg: Any) -> "DatasetDetectorOptions":
        r = CliResolver(args, cfg)
        return cls(
            pools      = r.get("pools",      "detection.pools",      []),
            skip_empty = r.get_bool("skip_empty", "detection.skip_empty", True),
            max_depth  = r.get("max_depth",  "detection.max_depth",  6,   cast=int),
            max_files  = r.get("max_files",  "detection.max_files",  2000,cast=int),
        )


@dataclass
class MountOptions:
    """Options pour core/zfs/mount.py"""
    boot_mount:    str  = ""
    no_automount:  bool = False
    force:         bool = False

    @classmethod
    def add_to_parser(cls, parser: argparse.ArgumentParser) -> None:
        g = parser.add_argument_group("montages")
        g.add_argument(
            "--boot-mount", metavar="CHEMIN",
            default="",
            help="Point de montage de boot_pool (défaut : /boot ou /mnt/zbm/boot)",
        )
        g.add_argument(
            "--no-automount",
            action="store_true", default=False,
            help="Ne pas monter les datasets automatiquement",
        )
        g.add_argument(
            "--force-mount",
            dest="force",
            action="store_true", default=False,
            help="Forcer le montage même si déjà monté",
        )

    @classmethod
    def resolve(cls, args: argparse.Namespace, cfg: Any) -> "MountOptions":
        r = CliResolver(args, cfg)
        return cls(
            boot_mount   = r.get("boot_mount",   "pool.boot_mount",   ""),
            no_automount = r.get_bool("no_automount", "mounts.no_automount", False),
            force        = r.get_bool("force",        "mounts.force",        False),
        )


@dataclass
class KernelOptions:
    """Options pour core/boot/kernel.py"""
    kernel_path:   str  = ""
    kernel_label:  str  = ""
    kernel_version:str  = ""
    modules_path:  str  = ""
    no_modules:    bool = False
    force:         bool = False

    @classmethod
    def add_to_parser(cls, parser: argparse.ArgumentParser) -> None:
        g = parser.add_argument_group("noyau")
        g.add_argument(
            "--kernel", metavar="CHEMIN",
            dest="kernel_path", default="",
            help="Chemin vers le noyau (vmlinuz) à utiliser",
        )
        g.add_argument(
            "--kernel-label", metavar="LABEL",
            default="",
            help="Label du noyau (ex: gentoo-6.6.47)",
        )
        g.add_argument(
            "--kernel-version", metavar="VERSION",
            default="",
            help="Version explicite du noyau (ex: 6.6.47-gentoo)",
        )
        g.add_argument(
            "--modules", metavar="CHEMIN",
            dest="modules_path", default="",
            help="Chemin vers les modules noyau (/lib/modules/<ver>)",
        )
        g.add_argument(
            "--no-modules",
            action="store_true", default=False,
            help="Ne pas packager de modules",
        )
        g.add_argument(
            "--force",
            action="store_true", default=False,
            help="Écraser si le fichier destination existe déjà",
        )

    @classmethod
    def resolve(cls, args: argparse.Namespace, cfg: Any) -> "KernelOptions":
        r = CliResolver(args, cfg)
        return cls(
            kernel_path    = r.get("kernel_path",    "kernel.active",       ""),
            kernel_label   = r.get("kernel_label",   "kernel.label",        ""),
            kernel_version = r.get("kernel_version", "kernel.version",      ""),
            modules_path   = r.get("modules_path",   "kernel.modules_path", ""),
            no_modules     = r.get_bool("no_modules","kernel.no_modules",   False),
            force          = r.get_bool("force",     "kernel.force",        False),
        )


@dataclass
class InitramfsOptions:
    """Options pour core/boot/initramfs.py"""
    init_type:     str       = "zbm"       # zbm | minimal | stream | custom
    kernel_version:str       = ""
    compress:      str       = "zstd"
    extra_drivers: list[str] = field(default_factory=list)
    extra_modules: list[str] = field(default_factory=list)
    force:         bool      = False
    init_file:     str       = ""          # init script custom (type=custom)

    @classmethod
    def add_to_parser(cls, parser: argparse.ArgumentParser) -> None:
        g = parser.add_argument_group("initramfs")
        g.add_argument(
            "--init-type",
            choices=["zbm", "minimal", "stream", "custom"],
            default="zbm",
            help="Type d'initramfs (défaut: zbm)",
        )
        g.add_argument(
            "--kernel-version", metavar="VERSION",
            dest="kernel_version", default="",
            help="Version du noyau pour dracut",
        )
        g.add_argument(
            "--compress",
            choices=["zstd", "xz", "gzip", "lz4"],
            default="zstd",
            help="Compression de l'initramfs (défaut: zstd)",
        )
        g.add_argument(
            "--extra-driver", nargs="+", metavar="MODULE",
            dest="extra_drivers", default=[],
            help="Modules noyau supplémentaires à inclure",
        )
        g.add_argument(
            "--extra-module", nargs="+", metavar="MODULE",
            dest="extra_modules", default=[],
            help="Modules dracut supplémentaires",
        )
        g.add_argument(
            "--init-file", metavar="CHEMIN",
            default="",
            help="Script init custom (pour --init-type=custom)",
        )
        g.add_argument(
            "--force",
            action="store_true", default=False,
            help="Écraser un initramfs existant",
        )

    @classmethod
    def resolve(cls, args: argparse.Namespace, cfg: Any) -> "InitramfsOptions":
        r = CliResolver(args, cfg)
        return cls(
            init_type      = r.get("init_type",      "initramfs.type",           "zbm"),
            kernel_version = r.get("kernel_version", "kernel.version",           ""),
            compress       = r.get("compress",       "initramfs.compress",       "zstd"),
            extra_drivers  = r.get("extra_drivers",  "initramfs.dracut_drivers", []),
            extra_modules  = r.get("extra_modules",  "initramfs.dracut_modules", []),
            force          = r.get_bool("force",     "initramfs.force",          False),
            init_file      = r.get("init_file",      "initramfs.init_file",      ""),
        )


@dataclass
class ZBMOptions:
    """Options pour core/boot/zbm.py"""
    efi_path:   str  = ""
    cmdline:    str  = ""
    timeout:    int  = 3
    bootfs:     str  = ""
    force:      bool = False

    @classmethod
    def add_to_parser(cls, parser: argparse.ArgumentParser) -> None:
        g = parser.add_argument_group("zfsbootmenu")
        g.add_argument(
            "--efi-path", metavar="CHEMIN",
            default="",
            help="Chemin relatif du binaire EFI dans la partition EFI",
        )
        g.add_argument(
            "--cmdline", metavar="OPTIONS",
            default="",
            help="Ligne de commande noyau pour ZFSBootMenu",
        )
        g.add_argument(
            "--timeout", metavar="SEC",
            type=int, default=3,
            help="Timeout ZFSBootMenu en secondes (défaut: 3)",
        )
        g.add_argument(
            "--bootfs", metavar="DATASET",
            default="",
            help="Dataset racine présenté par ZFSBootMenu",
        )
        g.add_argument(
            "--force",
            action="store_true", default=False,
            help="Écraser l'installation ZBM existante",
        )

    @classmethod
    def resolve(cls, args: argparse.Namespace, cfg: Any) -> "ZBMOptions":
        r = CliResolver(args, cfg)
        return cls(
            efi_path = r.get("efi_path", "zbm.efi_path", ""),
            cmdline  = r.get("cmdline",  "zbm.cmdline",  ""),
            timeout  = r.get("timeout",  "zbm.timeout",  3,  cast=int),
            bootfs   = r.get("bootfs",   "zbm.bootfs",   ""),
            force    = r.get_bool("force","zbm.force",   False),
        )


@dataclass
class StreamOptions:
    """Options pour core/stream.py"""
    youtube_key:   str  = ""
    resolution:    str  = "1920x1080"
    fps:           int  = 30
    bitrate:       str  = "4500k"
    audio_bitrate: str  = "128k"
    start_delay:   int  = 30
    enabled:       bool = False

    @classmethod
    def add_to_parser(cls, parser: argparse.ArgumentParser) -> None:
        g = parser.add_argument_group("stream youtube")
        g.add_argument(
            "--stream-key", metavar="CLE",
            dest="youtube_key", default="",
            help="Clé de stream YouTube RTMP",
        )
        g.add_argument(
            "--resolution",
            default="",
            help="Résolution vidéo (défaut: 1920x1080)",
        )
        g.add_argument(
            "--fps", metavar="N",
            type=int, default=0,
            help="Images par seconde (défaut: 30)",
        )
        g.add_argument(
            "--bitrate", metavar="VALEUR",
            default="",
            help="Débit vidéo (défaut: 4500k)",
        )
        g.add_argument(
            "--start-delay", metavar="SEC",
            dest="start_delay",
            type=int, default=0,
            help="Délai avant démarrage du stream en secondes (défaut: 30)",
        )
        g.add_argument(
            "--enable-stream",
            dest="enabled",
            action="store_true", default=False,
            help="Activer le stream au démarrage",
        )

    @classmethod
    def resolve(cls, args: argparse.Namespace, cfg: Any) -> "StreamOptions":
        r = CliResolver(args, cfg)
        return cls(
            youtube_key   = r.get("youtube_key",   "stream.youtube_key",   ""),
            resolution    = r.get("resolution",    "stream.resolution",    "1920x1080"),
            fps           = r.get("fps",           "stream.fps",           30,  cast=int),
            bitrate       = r.get("bitrate",       "stream.bitrate",       "4500k"),
            audio_bitrate = r.get("audio_bitrate", "stream.audio_bitrate", "128k"),
            start_delay   = r.get("start_delay",   "stream.start_delay",   30,  cast=int),
            enabled       = r.get_bool("enabled",  "stream.enabled",       False),
        )


@dataclass
class SnapshotOptions:
    """Options pour core/zfs/snapshot.py"""
    system:         str       = ""
    components:     list[str] = field(default_factory=list)
    retention_days: int       = 30
    compress:       bool      = True

    @classmethod
    def add_to_parser(cls, parser: argparse.ArgumentParser) -> None:
        g = parser.add_argument_group("snapshots")
        g.add_argument(
            "--system", metavar="NOM",
            default="",
            help="Système à snapshoter (ex: gentoo, systeme1)",
        )
        g.add_argument(
            "--component", nargs="+", metavar="NOM",
            dest="components", default=[],
            help="Composants à inclure (défaut: tous)",
        )
        g.add_argument(
            "--retention", metavar="JOURS",
            dest="retention_days",
            type=int, default=0,
            help="Rétention en jours (défaut: 30)",
        )
        g.add_argument(
            "--no-compress",
            dest="compress",
            action="store_false", default=True,
            help="Ne pas compresser les exports de snapshot",
        )

    @classmethod
    def resolve(cls, args: argparse.Namespace, cfg: Any) -> "SnapshotOptions":
        r = CliResolver(args, cfg)
        return cls(
            system         = r.get("system",         "snapshots.system",         ""),
            components     = r.get("components",     "snapshots.components",     []),
            retention_days = r.get("retention_days", "snapshots.retention_days", 30,  cast=int),
            compress       = r.get_bool("compress",  "snapshots.compress",       True),
        )


# =============================================================================
# HELPERS
# =============================================================================

def build_full_parser(description: str = "fsdeploy") -> argparse.ArgumentParser:
    """
    Construit un parser avec TOUTES les options (pour le point d'entrée principal).
    Chaque groupe d'options est visible dans --help.
    """
    parser = argparse.ArgumentParser(
        description     = description,
        formatter_class = argparse.RawDescriptionHelpFormatter,
    )
    GlobalOptions.add_to_parser(parser)
    PoolDetectorOptions.add_to_parser(parser)
    DatasetDetectorOptions.add_to_parser(parser)
    MountOptions.add_to_parser(parser)
    KernelOptions.add_to_parser(parser)
    InitramfsOptions.add_to_parser(parser)
    ZBMOptions.add_to_parser(parser)
    StreamOptions.add_to_parser(parser)
    SnapshotOptions.add_to_parser(parser)
    return parser


def resolve_all(
    args: argparse.Namespace,
    cfg: Any,
) -> dict[str, Any]:
    """
    Résout toutes les options d'un coup depuis args + cfg.
    Retourne un dict indexé par le nom de la dataclass.
    """
    return {
        "global":    GlobalOptions.from_args(args, cfg),
        "pool":      PoolDetectorOptions.resolve(args, cfg),
        "dataset":   DatasetDetectorOptions.resolve(args, cfg),
        "mount":     MountOptions.resolve(args, cfg),
        "kernel":    KernelOptions.resolve(args, cfg),
        "initramfs": InitramfsOptions.resolve(args, cfg),
        "zbm":       ZBMOptions.resolve(args, cfg),
        "stream":    StreamOptions.resolve(args, cfg),
        "snapshot":  SnapshotOptions.resolve(args, cfg),
    }
