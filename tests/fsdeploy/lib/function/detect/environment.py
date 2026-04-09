"""
fsdeploy.function.detect.environment
=====================================
Détection de l'environnement d'exécution.

Détermine :
  - live / booted / initramfs
  - init system (systemd / openrc / sysvinit / upstart)
  - hardware (CPU, RAM, disques)
  - réseau disponible
  - framebuffer (TERM=linux)
"""

import os
import platform
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from scheduler.model.task import Task
from scheduler.security.decorator import security


@dataclass
class EnvironmentInfo:
    """Résultat de la détection."""

    # Mode d'exécution
    mode: str = "unknown"           # live | booted | initramfs
    is_live: bool = False
    is_booted: bool = False
    is_initramfs: bool = False

    # Init system
    init_system: str = "unknown"    # systemd | openrc | sysvinit | upstart | none

    # Hardware
    arch: str = ""
    cpu_model: str = ""
    ram_mb: int = 0
    hostname: str = ""

    # Display
    is_framebuffer: bool = False
    term: str = ""

    # Network
    network_available: bool = False

    # Paths
    fsdeploy_dir: str = "/opt/fsdeploy"
    config_path: str = ""

    # Errors
    warnings: list[str] = field(default_factory=list)


@security.detect.environment
class EnvironmentDetectTask(Task):
    """
    Détecte l'environnement complet.
    Première task exécutée au démarrage.
    """

    def run(self) -> EnvironmentInfo:
        info = EnvironmentInfo()

        info.arch = platform.machine()
        info.hostname = platform.node()
        info.term = os.environ.get("TERM", "")
        info.is_framebuffer = info.term == "linux"
        info.fsdeploy_dir = os.environ.get("FSDEPLOY_INSTALL_DIR", "/opt/fsdeploy")

        # ── Mode détection ────────────────────────────────────────────
        info.is_live = self._detect_live()
        info.is_initramfs = self._detect_initramfs()
        info.is_booted = not info.is_live and not info.is_initramfs

        if info.is_initramfs:
            info.mode = "initramfs"
        elif info.is_live:
            info.mode = "live"
        else:
            info.mode = "booted"

        # ── Init system ───────────────────────────────────────────────
        info.init_system = self._detect_init_system()

        # ── Hardware ──────────────────────────────────────────────────
        info.cpu_model = self._get_cpu_model()
        info.ram_mb = self._get_ram_mb()

        # ── Network ───────────────────────────────────────────────────
        info.network_available = self._check_network()

        # ── Config path ───────────────────────────────────────────────
        info.config_path = self._find_config(info)

        return info

    def _detect_live(self) -> bool:
        """Heuristiques Debian Live."""
        cmdline = self._read_file("/proc/cmdline")
        if any(k in cmdline.lower() for k in ("boot=live", "live-media", "casper")):
            return True
        if Path("/run/live").is_dir():
            return True
        if Path("/etc/live/config").exists():
            return True
        # fstab quasi-vide
        fstab = self._read_file("/etc/fstab")
        entries = [l for l in fstab.splitlines()
                   if l.strip() and not l.strip().startswith("#")]
        if len(entries) < 3:
            return True
        return False

    def _detect_initramfs(self) -> bool:
        """Vrai si on est dans un initramfs."""
        # PID 1 est notre init, pas systemd/openrc
        if os.getpid() == 1:
            return True
        # /proc/1/cmdline contient "init" custom
        cmdline = self._read_file("/proc/1/cmdline")
        if "fsdeploy" in cmdline or "/init" == cmdline.split("\x00")[0]:
            return True
        # Pas de vrai rootfs monté
        if not Path("/etc/os-release").exists():
            return True
        return False

    def _detect_init_system(self, root: str = "/") -> str:
        """Détecte le système d'init."""
        r = Path(root)

        # systemd
        if (r / "run/systemd/system").is_dir():
            return "systemd"
        if (r / "usr/lib/systemd/systemd").exists():
            return "systemd"

        # openrc
        if (r / "sbin/openrc").exists() or (r / "usr/sbin/openrc").exists():
            return "openrc"

        # sysvinit
        if (r / "etc/init.d").is_dir() and not (r / "run/systemd/system").is_dir():
            return "sysvinit"

        # upstart
        if (r / "sbin/upstart").exists():
            return "upstart"

        return "none"

    def _get_cpu_model(self) -> str:
        cpuinfo = self._read_file("/proc/cpuinfo")
        for line in cpuinfo.splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
        return "unknown"

    def _get_ram_mb(self) -> int:
        meminfo = self._read_file("/proc/meminfo")
        for line in meminfo.splitlines():
            if line.startswith("MemTotal"):
                kb = int(line.split()[1])
                return kb // 1024
        return 0

    def _check_network(self) -> bool:
        """Vérifie si une interface réseau a une IP."""
        try:
            for iface_dir in Path("/sys/class/net").iterdir():
                name = iface_dir.name
                if name == "lo":
                    continue
                operstate = self._read_file(str(iface_dir / "operstate")).strip()
                if operstate == "up":
                    return True
        except OSError:
            pass
        return False

    def _find_config(self, info: EnvironmentInfo) -> str:
        """Cherche le fichier de config selon le contexte."""
        candidates = [
            os.environ.get("FSDEPLOY_CONFIG", ""),
            f"{info.fsdeploy_dir}/fsdeploy.conf",
            "/boot/fsdeploy/fsdeploy.conf",
            "/etc/fsdeploy/fsdeploy.conf",
            "/mnt/boot/fsdeploy/fsdeploy.conf",
        ]
        for path in candidates:
            if path and Path(path).is_file():
                return path
        return ""

    @staticmethod
    def _read_file(path: str) -> str:
        try:
            return Path(path).read_text(errors="replace")
        except OSError:
            return ""
