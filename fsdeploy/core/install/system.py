"""
fsdeploy.core.install.system
=============================
Remplace intégralement cron-tasks.sh.

SystemInstaller installe (et désinstalle) les composants système de fsdeploy
dans un rootfs cible :

  • Fichier cron (/etc/cron.d/fsdeploy-snapshots)
  • Configuration logrotate (/etc/logrotate.d/fsdeploy)
  • Service zbm-startup (openrc / systemd / sysvinit / runit)

PRINCIPE CLÉ — même code, trois contextes :

  Contexte               mountpoint          runner
  ─────────────────────  ──────────────────  ────────────────────────────
  Debian Live            Path("/mnt/target") CommandRunner(dry_run=False)
  Système installé CLI   Path("/")           CommandRunner(dry_run=False)
  UI Textual (booted)    Path("/")           runner fourni par l'écran

Le `runner` est toujours le même objet — ses lignes de log remontent
vers CommandLog dans l'UI ou vers structlog en CLI.

Usage :
    from pathlib import Path
    from fsdeploy.config import FsDeployConfig
    from fsdeploy.core.runner import CommandRunner
    from fsdeploy.core.install import SystemInstaller

    cfg     = FsDeployConfig.default()
    runner  = CommandRunner()
    inst    = SystemInstaller(cfg, runner, mountpoint=Path("/mnt/gentoo"))

    result = inst.install_all()      # tout
    result = inst.install_cron()     # seulement le cron
    result = inst.install_service()  # seulement le service
    result = inst.install_logrotate()
    result = inst.uninstall_all()    # désinstallation propre
    status = inst.status()           # état courant (dict)
"""

from __future__ import annotations

import os
import shutil
import stat
import tempfile
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Callable, Iterator

from fsdeploy.config import FsDeployConfig
from fsdeploy.core.install.detect import InitSystem, detect_init_system, detect_init_system_verbose
from fsdeploy.core.runner import CommandRunner


# =============================================================================
# TYPES RÉSULTAT
# =============================================================================

class InstallStatus(Enum):
    OK       = "ok"
    SKIPPED  = "skipped"    # déjà présent et identique
    UPDATED  = "updated"    # présent mais remplacé
    FAILED   = "failed"
    DRY_RUN  = "dry_run"


@dataclass
class InstallResult:
    """
    Résultat d'une opération d'installation.
    Agrège les résultats des sous-opérations (cron, service, logrotate).
    """
    component:  str                       # "cron" | "service" | "logrotate" | "all"
    status:     InstallStatus
    path:       Path | None = None        # fichier installé
    init:       InitSystem | None = None  # init détecté (pour service)
    message:    str = ""
    errors:     list[str] = field(default_factory=list)
    sub:        list["InstallResult"] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status in (InstallStatus.OK, InstallStatus.UPDATED,
                               InstallStatus.SKIPPED, InstallStatus.DRY_RUN)

    @property
    def summary(self) -> str:
        icon = {
            InstallStatus.OK:      "✅",
            InstallStatus.SKIPPED: "⏭ ",
            InstallStatus.UPDATED: "🔄",
            InstallStatus.FAILED:  "❌",
            InstallStatus.DRY_RUN: "🔍",
        }[self.status]
        path_str = f" → {self.path}" if self.path else ""
        return f"{icon} {self.component}{path_str} : {self.message or self.status.value}"


# =============================================================================
# TEMPLATES DE FICHIERS
# =============================================================================

def _cron_content(fsdeploy_cmd: str) -> str:
    """
    Contenu du fichier /etc/cron.d/fsdeploy-snapshots.
    `fsdeploy_cmd` = chemin complet vers l'exécutable (python ou wrapper).
    """
    return f"""\
# fsdeploy — Snapshots planifiés
# Généré par fsdeploy.core.install.system — NE PAS ÉDITER À LA MAIN
# Pour modifier, utiliser : fsdeploy install-cron ou l'UI fsdeploy

# Vérification toutes les heures (fsdeploy décide si un profil est échu)
0 * * * *   root   {fsdeploy_cmd} snapshot --run-scheduled >> /var/log/fsdeploy-cron.log 2>&1

# Archivage mensuel (1er du mois à 5h)
0 5 1 * *   root   {fsdeploy_cmd} snapshot --archive-monthly >> /var/log/fsdeploy-cron.log 2>&1
"""


def _logrotate_content() -> str:
    return """\
# fsdeploy — Rotation des logs
# Généré par fsdeploy.core.install.system — NE PAS ÉDITER À LA MAIN
/var/log/fsdeploy-cron.log
/var/log/zbm-startup.log
{
    weekly
    rotate 8
    compress
    delaycompress
    missingok
    notifempty
    create 640 root root
}
"""


def _openrc_service_content() -> str:
    return """\
#!/sbin/openrc-run
# fsdeploy zbm-startup — service OpenRC
# Généré par fsdeploy.core.install.system

description="fsdeploy ZFSBootMenu startup tasks"
command="/opt/fsdeploy/.venv/bin/python3"
command_args="-m fsdeploy zbm-startup"
command_background="no"
pidfile="/run/${RC_SVCNAME}.pid"

depend() {
    need localmount
    after zfs-mount net
}

start_pre() {
    checkpath --directory --owner root:root --mode 0755 /run/fsdeploy
}
"""


def _systemd_unit_content() -> str:
    return """\
[Unit]
Description=fsdeploy ZFSBootMenu startup tasks
After=local-fs.target zfs-mount.service network.target
Requires=local-fs.target

[Service]
Type=oneshot
ExecStart=/opt/fsdeploy/.venv/bin/python3 -m fsdeploy zbm-startup
RemainAfterExit=yes
StandardOutput=journal
StandardError=journal
SyslogIdentifier=fsdeploy-zbm

[Install]
WantedBy=multi-user.target
"""


def _sysvinit_service_content() -> str:
    return """\
#!/bin/sh
### BEGIN INIT INFO
# Provides:          zbm-startup
# Required-Start:    $local_fs $remote_fs
# Required-Stop:
# Default-Start:     2 3 4 5
# Default-Stop:      0 1 6
# Short-Description: fsdeploy ZFSBootMenu startup tasks
### END INIT INFO
# Généré par fsdeploy.core.install.system

PATH=/sbin:/bin:/usr/sbin:/usr/bin
DAEMON=/opt/fsdeploy/.venv/bin/python3
DAEMON_ARGS="-m fsdeploy zbm-startup"
NAME=zbm-startup

case "$1" in
  start)
    echo "Starting $NAME"
    $DAEMON $DAEMON_ARGS
    ;;
  stop|restart|force-reload)
    echo "$NAME is a oneshot service — no stop action"
    ;;
  status)
    echo "$NAME: oneshot (always done)"
    ;;
  *)
    echo "Usage: $0 {start|stop|status}" >&2
    exit 3
    ;;
esac
exit 0
"""


def _runit_run_content() -> str:
    return """\
#!/bin/sh
exec /opt/fsdeploy/.venv/bin/python3 -m fsdeploy zbm-startup 2>&1
"""


# =============================================================================
# SERVICE METADATA PAR INIT SYSTEM
# =============================================================================

@dataclass
class _ServiceSpec:
    """Décrit où et comment installer le service selon l'init."""
    init:        InitSystem
    target_path: Path          # chemin relatif à la racine du rootfs
    content_fn:  Callable[[], str]
    executable:  bool          # True → chmod +x
    service_name: str = "zbm-startup"


_SERVICE_SPECS: dict[InitSystem, _ServiceSpec] = {
    InitSystem.OPENRC: _ServiceSpec(
        init=InitSystem.OPENRC,
        target_path=Path("etc/init.d/zbm-startup"),
        content_fn=_openrc_service_content,
        executable=True,
    ),
    InitSystem.SYSTEMD: _ServiceSpec(
        init=InitSystem.SYSTEMD,
        target_path=Path("etc/systemd/system/zbm-startup.service"),
        content_fn=_systemd_unit_content,
        executable=False,
    ),
    InitSystem.SYSVINIT: _ServiceSpec(
        init=InitSystem.SYSVINIT,
        target_path=Path("etc/init.d/zbm-startup"),
        content_fn=_sysvinit_service_content,
        executable=True,
    ),
    InitSystem.RUNIT: _ServiceSpec(
        init=InitSystem.RUNIT,
        target_path=Path("etc/sv/zbm-startup/run"),
        content_fn=_runit_run_content,
        executable=True,
    ),
}


# =============================================================================
# SYSTEM INSTALLER
# =============================================================================

class SystemInstaller:
    """
    Installe les composants système de fsdeploy dans un rootfs.

    Args:
        cfg:        Instance FsDeployConfig — source de vérité pour les chemins.
        runner:     CommandRunner — toutes les commandes passent par lui.
        mountpoint: Racine du rootfs cible.
                    Path("/")           → système courant (live ou booté)
                    Path("/mnt/target") → rootfs monté depuis le live
        on_progress: Callback optionnel appelé à chaque étape :
                     fn(step: str, detail: str) → None
                     Utilisé par InstallScreen pour mettre à jour l'UI.
    """

    CRON_PATH     = Path("etc/cron.d/fsdeploy-snapshots")
    LOGROTATE_PATH = Path("etc/logrotate.d/fsdeploy")
    LOG_DIR       = Path("var/log")
    FSDEPLOY_CMD  = "/opt/fsdeploy/.venv/bin/python3 -m fsdeploy"

    def __init__(
        self,
        cfg: FsDeployConfig,
        runner: CommandRunner,
        mountpoint: Path | str = Path("/"),
        on_progress: Callable[[str, str], None] | None = None,
    ) -> None:
        self.cfg         = cfg
        self.runner      = runner
        self.mountpoint  = Path(mountpoint)
        self.on_progress = on_progress or (lambda s, d: None)
        self._init: InitSystem | None = None   # cache détection

    # ── Propriétés ───────────────────────────────────────────────────────────

    @property
    def is_live(self) -> bool:
        """True si on installe dans un rootfs tiers (live installer)."""
        return self.mountpoint != Path("/")

    @property
    def init_system(self) -> InitSystem:
        """Détection du système init (résultat mis en cache)."""
        if self._init is None:
            self._init = detect_init_system(self.mountpoint)
        return self._init

    def _abs(self, relative: Path) -> Path:
        """Chemin absolu dans le rootfs cible."""
        return self.mountpoint / relative

    # ── API principale ───────────────────────────────────────────────────────

    def install_all(self) -> InstallResult:
        """
        Installe l'ensemble des composants système.
        Retourne un InstallResult agrégé avec les sous-résultats.
        """
        self._progress("install_all", f"Rootfs : {self.mountpoint}")
        results = []

        for fn, name in [
            (self.install_cron,      "cron"),
            (self.install_logrotate, "logrotate"),
            (self.install_service,   "service"),
        ]:
            try:
                r = fn()
                results.append(r)
            except Exception as exc:
                results.append(InstallResult(
                    component=name,
                    status=InstallStatus.FAILED,
                    errors=[str(exc)],
                    message=str(exc),
                ))

        all_ok = all(r.ok for r in results)
        errors = [e for r in results for e in r.errors]

        return InstallResult(
            component="all",
            status=InstallStatus.OK if all_ok else InstallStatus.FAILED,
            message="Installation complète" if all_ok else "Erreurs partielles",
            errors=errors,
            sub=results,
        )

    def install_cron(self) -> InstallResult:
        """Installe /etc/cron.d/fsdeploy-snapshots dans le rootfs."""
        self._progress("install_cron", "Installation du fichier cron")

        target = self._abs(self.CRON_PATH)
        content = _cron_content(self.FSDEPLOY_CMD)

        return self._write_config_file(
            component="cron",
            target=target,
            content=content,
            mode=0o644,
        )

    def install_logrotate(self) -> InstallResult:
        """Installe /etc/logrotate.d/fsdeploy dans le rootfs."""
        self._progress("install_logrotate", "Installation logrotate")

        target = self._abs(self.LOGROTATE_PATH)
        content = _logrotate_content()

        return self._write_config_file(
            component="logrotate",
            target=target,
            content=content,
            mode=0o644,
        )

    def install_service(self) -> InstallResult:
        """
        Installe et active le service zbm-startup selon l'init détecté.

        Pour un rootfs live (mountpoint != /), utilise chroot pour
        activer le service si l'init system le permet.
        """
        init = self.init_system
        self._progress(
            "install_service",
            f"Init détecté : {init.label} — installation zbm-startup",
        )

        # Verbose diagnostic dans le log runner
        self.runner.log_info(
            "detect_init",
            f"Détection init système dans {self.mountpoint} : {init.label}",
        )

        if init == InitSystem.UNKNOWN:
            return InstallResult(
                component="service",
                status=InstallStatus.FAILED,
                init=init,
                message="Système init non reconnu — installation manuelle requise",
                errors=["init_unknown"],
            )

        spec = _SERVICE_SPECS.get(init)
        if spec is None:
            return InstallResult(
                component="service",
                status=InstallStatus.FAILED,
                init=init,
                message=f"Aucun spec service pour {init.label}",
                errors=[f"no_spec:{init.value}"],
            )

        # 1. Créer le répertoire parent si besoin (ex: /etc/sv/zbm-startup/)
        target = self._abs(spec.target_path)
        self._ensure_dir(target.parent, mode=0o755)

        # 2. Écrire le fichier de service
        write_result = self._write_config_file(
            component="service",
            target=target,
            content=spec.content_fn(),
            mode=0o755 if spec.executable else 0o644,
        )
        if not write_result.ok:
            return write_result

        # 3. Activer le service
        enable_result = self._enable_service(init, spec)

        # Résultat agrégé
        sub = [write_result, enable_result]
        all_ok = all(r.ok for r in sub)
        return InstallResult(
            component="service",
            status=InstallStatus.OK if all_ok else InstallStatus.FAILED,
            path=target,
            init=init,
            message=f"Service zbm-startup ({init.label})"
                    + (" activé" if enable_result.ok else " — activation manuelle requise"),
            errors=[e for r in sub for e in r.errors],
            sub=sub,
        )

    def uninstall_all(self) -> InstallResult:
        """
        Désinstalle proprement tous les composants installés par fsdeploy.
        Demande confirmation via runner si des fichiers existent.
        """
        self._progress("uninstall_all", "Désinstallation fsdeploy system components")
        results = []

        for component, path in [
            ("cron",      self._abs(self.CRON_PATH)),
            ("logrotate", self._abs(self.LOGROTATE_PATH)),
        ]:
            results.append(self._remove_file(component, path))

        # Service selon l'init
        init = self.init_system
        spec = _SERVICE_SPECS.get(init)
        if spec:
            service_path = self._abs(spec.target_path)
            # Désactiver d'abord
            disable_cmd = init.disable_cmd(spec.service_name)
            if disable_cmd and service_path.exists():
                self._run_chroot_or_direct(disable_cmd, "disable_service")
            results.append(self._remove_file("service", service_path))

            # Runit : supprimer aussi le répertoire sv/zbm-startup
            if init == InitSystem.RUNIT:
                sv_dir = self._abs(Path("etc/sv/zbm-startup"))
                if sv_dir.is_dir():
                    self.runner.log_info("uninstall", f"rmdir {sv_dir}")
                    if not self.runner.dry_run:
                        shutil.rmtree(sv_dir, ignore_errors=True)

        all_ok = all(r.ok for r in results)
        return InstallResult(
            component="uninstall_all",
            status=InstallStatus.OK if all_ok else InstallStatus.FAILED,
            message="Désinstallation complète" if all_ok else "Erreurs partielles",
            errors=[e for r in results for e in r.errors],
            sub=results,
        )

    def status(self) -> dict:
        """
        Retourne l'état de l'installation (sans modifier le système).
        Utilisé par l'UI pour afficher l'état courant.

        Returns:
            {
                "mountpoint": str,
                "is_live":    bool,
                "init":       str,           # InitSystem.value
                "init_label": str,
                "components": {
                    "cron":      {"installed": bool, "path": str, "size": int},
                    "logrotate": {"installed": bool, "path": str, "size": int},
                    "service":   {"installed": bool, "path": str, "executable": bool},
                },
                "all_installed": bool,
            }
        """
        init = self.init_system
        spec = _SERVICE_SPECS.get(init)

        cron_path      = self._abs(self.CRON_PATH)
        logrotate_path = self._abs(self.LOGROTATE_PATH)
        service_path   = self._abs(spec.target_path) if spec else None

        def _file_info(p: Path | None) -> dict:
            if p is None or not p.exists():
                return {"installed": False, "path": str(p or ""), "size": 0}
            s = p.stat()
            return {
                "installed":   True,
                "path":        str(p),
                "size":        s.st_size,
                "executable":  bool(s.st_mode & stat.S_IXUSR),
            }

        cron_info      = _file_info(cron_path)
        logrotate_info = _file_info(logrotate_path)
        service_info   = _file_info(service_path)

        all_installed = (
            cron_info["installed"]
            and logrotate_info["installed"]
            and service_info["installed"]
        )

        verbose = detect_init_system_verbose(self.mountpoint)

        return {
            "mountpoint":    str(self.mountpoint),
            "is_live":       self.is_live,
            "init":          init.value,
            "init_label":    init.label,
            "init_detection": verbose,
            "components": {
                "cron":      cron_info,
                "logrotate": logrotate_info,
                "service":   service_info,
            },
            "all_installed": all_installed,
        }

    # ── Helpers internes ─────────────────────────────────────────────────────

    def _progress(self, step: str, detail: str) -> None:
        """Notifie le callback de progression (UI) et logge."""
        self.on_progress(step, detail)
        self.runner.log_info(step, detail)

    def _ensure_dir(self, path: Path, mode: int = 0o755) -> None:
        """Crée un répertoire (et ses parents) si inexistant."""
        if not path.exists():
            self.runner.log_info("mkdir", str(path))
            if not self.runner.dry_run:
                path.mkdir(parents=True, exist_ok=True)
                path.chmod(mode)

    def _write_config_file(
        self,
        component: str,
        target: Path,
        content: str,
        mode: int,
    ) -> InstallResult:
        """
        Écrit un fichier de configuration de manière atomique.

        - Si le fichier existe et est identique → SKIPPED
        - Si le fichier existe et diffère       → UPDATED (log du diff)
        - Si le fichier n'existe pas            → OK
        - En dry_run                            → DRY_RUN (rien n'est écrit)
        """
        self._ensure_dir(target.parent)

        exists   = target.exists()
        same     = exists and target.read_text(encoding="utf-8") == content
        action   = "identique" if same else ("mise à jour" if exists else "création")

        self.runner.log_info(
            f"write.{component}",
            f"{action} : {target}",
        )

        if same:
            return InstallResult(
                component=component,
                status=InstallStatus.SKIPPED,
                path=target,
                message=f"Déjà à jour : {target}",
            )

        if self.runner.dry_run:
            return InstallResult(
                component=component,
                status=InstallStatus.DRY_RUN,
                path=target,
                message=f"[dry_run] {action} : {target}",
            )

        # Écriture atomique via fichier temporaire dans le même répertoire
        # (garantit pas de fichier à moitié écrit si le processus est tué)
        try:
            tmp_fd, tmp_path = tempfile.mkstemp(
                dir=target.parent,
                prefix=f".fsdeploy_{component}_",
            )
            try:
                with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                    f.write(content)
                os.chmod(tmp_path, mode)
                os.replace(tmp_path, target)   # atomique sur même filesystem
            except Exception:
                os.unlink(tmp_path)
                raise
        except Exception as exc:
            return InstallResult(
                component=component,
                status=InstallStatus.FAILED,
                path=target,
                message=str(exc),
                errors=[str(exc)],
            )

        self.runner.log_info(
            f"write.{component}.ok",
            f"{'✅ Mis à jour' if exists else '✅ Créé'} : {target}",
        )

        return InstallResult(
            component=component,
            status=InstallStatus.UPDATED if exists else InstallStatus.OK,
            path=target,
            message=f"{'Mis à jour' if exists else 'Installé'} : {target}",
        )

    def _enable_service(
        self,
        init: InitSystem,
        spec: "_ServiceSpec",
    ) -> InstallResult:
        """
        Active le service dans le rootfs.

        Live (mountpoint != /)  → chroot + commande d'activation
        Système courant (/)     → commande d'activation directe
        Runit                   → symlink /var/service → /etc/sv/
        init non supporté       → SKIPPED avec message
        """
        enable_cmd = init.enable_cmd(spec.service_name)

        if not enable_cmd:
            return InstallResult(
                component="service.enable",
                status=InstallStatus.SKIPPED,
                init=init,
                message=f"{init.label} : activation manuelle requise",
            )

        # Runit : pas de commande — on fait un symlink
        if init == InitSystem.RUNIT:
            return self._enable_runit(spec)

        ok = self._run_chroot_or_direct(enable_cmd, "service.enable")
        return InstallResult(
            component="service.enable",
            status=InstallStatus.OK if ok else InstallStatus.FAILED,
            init=init,
            message=" ".join(enable_cmd) if ok else "Échec activation",
            errors=[] if ok else ["enable_failed"],
        )

    def _enable_runit(self, spec: "_ServiceSpec") -> InstallResult:
        """Activation runit : symlink /var/service/zbm-startup → /etc/sv/zbm-startup."""
        sv_dir     = self._abs(Path(f"etc/sv/{spec.service_name}"))
        link_dir   = self._abs(Path(f"var/service/{spec.service_name}"))

        self._ensure_dir(self._abs(Path("var/service")))

        if link_dir.is_symlink():
            self.runner.log_info("runit.enable", f"Symlink déjà présent : {link_dir}")
            return InstallResult(
                component="service.enable",
                status=InstallStatus.SKIPPED,
                init=InitSystem.RUNIT,
                message=f"Symlink déjà présent : {link_dir}",
            )

        self.runner.log_info(
            "runit.enable",
            f"ln -s {sv_dir} {link_dir}",
        )
        if not self.runner.dry_run:
            link_dir.symlink_to(sv_dir)

        return InstallResult(
            component="service.enable",
            status=InstallStatus.OK,
            init=InitSystem.RUNIT,
            message=f"Symlink créé : {link_dir} → {sv_dir}",
        )

    def _run_chroot_or_direct(
        self,
        cmd: list[str],
        log_key: str,
    ) -> bool:
        """
        Exécute une commande :
        - directement si mountpoint == /
        - via chroot <mountpoint> si rootfs tiers

        Retourne True si succès.
        """
        if self.is_live:
            full_cmd = ["chroot", str(self.mountpoint)] + cmd
        else:
            full_cmd = cmd

        self.runner.log_info(log_key, " ".join(full_cmd))

        if self.runner.dry_run:
            return True

        try:
            for line in self.runner.run(full_cmd):
                self.runner.log_info(log_key, line)
            return True
        except Exception as exc:
            self.runner.log_error(log_key, str(exc))
            return False

    def _remove_file(self, component: str, path: Path) -> InstallResult:
        """Supprime un fichier installé."""
        if not path.exists():
            return InstallResult(
                component=f"remove.{component}",
                status=InstallStatus.SKIPPED,
                path=path,
                message=f"Absent : {path}",
            )

        self.runner.log_info(f"remove.{component}", f"Suppression : {path}")

        if self.runner.dry_run:
            return InstallResult(
                component=f"remove.{component}",
                status=InstallStatus.DRY_RUN,
                path=path,
                message=f"[dry_run] Suppression : {path}",
            )

        try:
            path.unlink()
            return InstallResult(
                component=f"remove.{component}",
                status=InstallStatus.OK,
                path=path,
                message=f"Supprimé : {path}",
            )
        except Exception as exc:
            return InstallResult(
                component=f"remove.{component}",
                status=InstallStatus.FAILED,
                path=path,
                message=str(exc),
                errors=[str(exc)],
            )
