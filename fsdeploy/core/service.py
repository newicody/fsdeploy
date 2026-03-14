"""
fsdeploy.core.service
======================
Détection du système init et gestion/installation des services.
Supporte : systemd, OpenRC, sysvinit/init.d

Un seul fichier, une fonction de détection, trois branches if/elif/else.
Pas de sur-ingénierie : l'usage réel est d'activer un service une fois
lors du déploiement dans un rootfs cible.

Usage :
    from fsdeploy.core.service import detect_init, ServiceManager, Init

    # Détection du rootfs CIBLE (monté sur /mnt/gentoo par ex.)
    init = detect_init(root=Path("/mnt/gentoo"))

    sm = ServiceManager(init)
    ok, msg = sm.install("zbm-startup", source_dir=Path("system/"))
    ok, msg = sm.enable("zbm-startup")

    # Ou en une seule opération
    ok, msg = sm.install_and_enable("zbm-startup", source_dir=Path("system/"))

    # Sur le système courant (post-boot)
    sm = ServiceManager()           # détection automatique du PID 1
    ok, msg = sm.start("zbm-startup")
    ok, msg = sm.status("zbm-startup")
"""

from __future__ import annotations

import shutil
import subprocess
from enum import Enum
from pathlib import Path


# =============================================================================
# DÉTECTION
# =============================================================================

class Init(str, Enum):
    SYSTEMD  = "systemd"
    OPENRC   = "openrc"
    SYSVINIT = "sysvinit"
    NONE     = "none"       # initramfs / live sans init


def detect_init(root: Path | None = None) -> Init:
    """
    Détecte le système init.

    Si root est fourni (ex: Path("/mnt/gentoo")), inspecte le rootfs cible
    monté à cet endroit — utile lors du déploiement.

    Si root est None, détecte l'init du système courant via /proc/1.

    Ordre de priorité :
      1. /proc/1/comm  (système courant uniquement)
      2. Présence de fichiers runtime (/run/systemd, /run/openrc)
      3. Binaires et répertoires dans le rootfs cible
    """
    if root is None:
        # ── Système courant ──────────────────────────────────────────────────
        try:
            comm = Path("/proc/1/comm").read_text().strip().lower()
            if "systemd" in comm:
                return Init.SYSTEMD
            if "openrc" in comm:
                return Init.OPENRC
            if comm in ("init", "sysvinit", "busybox"):
                return Init.SYSVINIT
        except OSError:
            pass

        if Path("/run/systemd/private").exists():
            return Init.SYSTEMD
        if Path("/run/openrc").exists():
            return Init.OPENRC
        if shutil.which("systemctl") and not shutil.which("rc-service"):
            return Init.SYSTEMD
        if shutil.which("rc-service"):
            return Init.OPENRC
        if shutil.which("service") and Path("/etc/init.d").is_dir():
            return Init.SYSVINIT
        return Init.NONE

    # ── Rootfs cible (déploiement) ────────────────────────────────────────────
    if (root / "sbin" / "openrc").exists() or \
       (root / "sbin" / "openrc-init").exists() or \
       (root / "etc" / "gentoo-release").exists() or \
       (root / "etc" / "alpine-release").exists():
        return Init.OPENRC

    if (root / "etc" / "systemd").is_dir() or \
       (root / "lib" / "systemd" / "systemd").exists() or \
       (root / "usr" / "lib" / "systemd" / "systemd").exists():
        return Init.SYSTEMD

    if (root / "etc" / "init.d").is_dir():
        return Init.SYSVINIT

    return Init.NONE


# =============================================================================
# SERVICE MANAGER
# =============================================================================

class ServiceManager:
    """
    API unifiée start / stop / enable / install — quel que soit l'init.
    Chaque méthode retourne (success: bool, message: str).

        sm = ServiceManager()                          # init auto (système courant)
        sm = ServiceManager(Init.OPENRC)               # init explicite
        sm = ServiceManager(detect_init(Path("/mnt"))) # init du rootfs cible
    """

    def __init__(self, init: Init | None = None) -> None:
        self.init = init if init is not None else detect_init()

    # ── Interne ──────────────────────────────────────────────────────────────

    def _run(self, cmd: list[str]) -> tuple[bool, str]:
        try:
            r = subprocess.run(cmd, capture_output=True, text=True)
            out = (r.stdout + r.stderr).strip()
            return r.returncode == 0, out
        except FileNotFoundError as exc:
            return False, f"Commande introuvable : {exc}"

    def _chroot_run(self, root: Path, cmd: list[str]) -> tuple[bool, str]:
        return self._run(["chroot", str(root)] + cmd)

    # ── Actions (système courant) ─────────────────────────────────────────────

    def start(self, svc: str) -> tuple[bool, str]:
        if self.init == Init.SYSTEMD:  return self._run(["systemctl", "start",   svc])
        if self.init == Init.OPENRC:   return self._run(["rc-service", svc, "start"])
        if self.init == Init.SYSVINIT: return self._run(["service",    svc, "start"])
        return False, f"init={self.init.value} — start non supporté"

    def stop(self, svc: str) -> tuple[bool, str]:
        if self.init == Init.SYSTEMD:  return self._run(["systemctl", "stop",    svc])
        if self.init == Init.OPENRC:   return self._run(["rc-service", svc, "stop"])
        if self.init == Init.SYSVINIT: return self._run(["service",    svc, "stop"])
        return False, f"init={self.init.value} — stop non supporté"

    def restart(self, svc: str) -> tuple[bool, str]:
        if self.init == Init.SYSTEMD:  return self._run(["systemctl", "restart",  svc])
        if self.init == Init.OPENRC:   return self._run(["rc-service", svc, "restart"])
        if self.init == Init.SYSVINIT: return self._run(["service",    svc, "restart"])
        return False, f"init={self.init.value} — restart non supporté"

    def status(self, svc: str) -> tuple[bool, str]:
        """Retourne (is_running, message)."""
        if self.init == Init.SYSTEMD:
            return self._run(["systemctl", "is-active", "--quiet", svc])
        if self.init == Init.OPENRC:
            ok, out = self._run(["rc-service", svc, "status"])
            return "started" in out.lower(), out
        if self.init == Init.SYSVINIT:
            return self._run(["service", svc, "status"])
        return False, "init non détecté"

    # ── Activation au démarrage ──────────────────────────────────────────────

    def enable(self, svc: str, runlevel: str = "default",
               root: Path | None = None) -> tuple[bool, str]:
        """
        Active le service au démarrage.
        Si root est fourni, l'activation se fait dans le rootfs cible via chroot.
        """
        run = (lambda cmd: self._chroot_run(root, cmd)) if root else self._run

        if self.init == Init.SYSTEMD:
            return run(["systemctl", "enable", svc])
        if self.init == Init.OPENRC:
            return run(["rc-update", "add", svc, runlevel])
        if self.init == Init.SYSVINIT:
            if shutil.which("update-rc.d") or (root and (root / "usr/sbin/update-rc.d").exists()):
                return run(["update-rc.d", svc, "defaults"])
            if shutil.which("chkconfig") or (root and (root / "sbin/chkconfig").exists()):
                return run(["chkconfig", svc, "on"])
            return False, "update-rc.d / chkconfig introuvable"
        return False, "enable non supporté (init non détecté)"

    def disable(self, svc: str, runlevel: str = "default",
                root: Path | None = None) -> tuple[bool, str]:
        run = (lambda cmd: self._chroot_run(root, cmd)) if root else self._run

        if self.init == Init.SYSTEMD:
            return run(["systemctl", "disable", svc])
        if self.init == Init.OPENRC:
            return run(["rc-update", "del", svc, runlevel])
        if self.init == Init.SYSVINIT:
            if shutil.which("update-rc.d") or (root and (root / "usr/sbin/update-rc.d").exists()):
                return run(["update-rc.d", svc, "disable"])
            if shutil.which("chkconfig") or (root and (root / "sbin/chkconfig").exists()):
                return run(["chkconfig", svc, "off"])
            return False, "update-rc.d / chkconfig introuvable"
        return False, "disable non supporté (init non détecté)"

    # ── Installation du fichier de service ───────────────────────────────────

    def install(self, svc: str, source_dir: Path,
                root: Path | None = None) -> tuple[bool, str]:
        """
        Copie le fichier de service depuis source_dir vers le bon répertoire.

        Convention de nommage dans source_dir (repo fsdeploy/system/) :
          <svc>          → OpenRC  → /etc/init.d/<svc>
          <svc>.service  → systemd → /etc/systemd/system/<svc>.service
          <svc>.init.d   → sysvinit → /etc/init.d/<svc>

        root : racine du rootfs cible (None = système courant).
        """
        prefix = root or Path("/")

        if self.init == Init.SYSTEMD:
            src = source_dir / f"{svc}.service"
            if not src.exists():
                return False, f"Fichier systemd absent : {src}"
            dst = prefix / "etc/systemd/system" / f"{svc}.service"
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            dst.chmod(0o644)
            return True, f"Installé → {dst}"

        if self.init == Init.OPENRC:
            src = source_dir / svc
            if not src.exists():
                return False, f"Fichier OpenRC absent : {src}"
            dst = prefix / "etc/init.d" / svc
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            dst.chmod(0o755)
            return True, f"Installé → {dst}"

        if self.init == Init.SYSVINIT:
            src = source_dir / f"{svc}.init.d"
            if not src.exists():
                src = source_dir / svc      # fallback : même fichier qu'OpenRC
            if not src.exists():
                return False, f"Fichier sysvinit absent : {source_dir / f'{svc}.init.d'}"
            dst = prefix / "etc/init.d" / svc
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            dst.chmod(0o755)
            return True, f"Installé → {dst}"

        return False, f"init={self.init.value} — install non supporté"

    def install_and_enable(
        self,
        svc:        str,
        source_dir: Path,
        root:       Path | None = None,
        runlevel:   str         = "default",
    ) -> tuple[bool, str]:
        """Installe le fichier de service ET l'active au démarrage."""
        ok, msg = self.install(svc, source_dir, root)
        if not ok:
            return False, msg
        ok2, msg2 = self.enable(svc, runlevel, root)
        return ok2, f"{msg} | {msg2}"
