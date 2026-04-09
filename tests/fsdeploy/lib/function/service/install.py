"""
fsdeploy.function.service.install
==================================
Installe fsdeploy comme service système.

Un seul service installé, détection de l'init system.
Le scheduler Python interne gère tout le reste.
"""

from pathlib import Path
from typing import Any

from scheduler.model.task import Task
from scheduler.security.decorator import security


SYSTEMD_UNIT = """\
[Unit]
Description=fsdeploy ZFS boot manager
After=zfs.target network-online.target
Wants=zfs.target

[Service]
Type=simple
ExecStart={venv}/bin/python3 -m fsdeploy --daemon
Restart=on-failure
RestartSec=5
User={user}
Group=fsdeploy
Environment=FSDEPLOY_INSTALL_DIR={install_dir}

[Install]
WantedBy=multi-user.target
"""

OPENRC_SCRIPT = """\
#!/sbin/openrc-run
description="fsdeploy ZFS boot manager"
command="{venv}/bin/python3"
command_args="-m fsdeploy --daemon"
command_user="{user}:fsdeploy"
command_background=true
pidfile="/run/fsdeploy.pid"
depend() {{
    need net zfs
    after zfs
}}
"""

SYSVINIT_SCRIPT = """\
#!/bin/sh
### BEGIN INIT INFO
# Provides:          fsdeploy
# Required-Start:    $network $local_fs zfs-mount
# Required-Stop:     $network $local_fs
# Default-Start:     2 3 4 5
# Default-Stop:      0 1 6
# Description:       fsdeploy ZFS boot manager
### END INIT INFO

DAEMON="{venv}/bin/python3"
DAEMON_ARGS="-m fsdeploy --daemon"
PIDFILE="/run/fsdeploy.pid"
USER="{user}"

case "$1" in
    start)
        start-stop-daemon --start --background --make-pidfile \\
            --pidfile "$PIDFILE" --chuid "$USER" --exec "$DAEMON" -- $DAEMON_ARGS
        ;;
    stop)
        start-stop-daemon --stop --pidfile "$PIDFILE" --retry=TERM/30/KILL/5
        ;;
    restart)
        $0 stop && $0 start
        ;;
    status)
        start-stop-daemon --status --pidfile "$PIDFILE"
        ;;
    *)
        echo "Usage: $0 {{start|stop|restart|status}}"
        exit 1
        ;;
esac
"""


@security.service.install(require_root=True)
class ServiceInstallTask(Task):
    """Installe fsdeploy comme service système."""

    def run(self) -> dict[str, Any]:
        init_system = self.params.get("init_system", "")
        user = self.params.get("user", "root")
        install_dir = self.params.get("install_dir", "/opt/fsdeploy")
        venv = self.params.get("venv", f"{install_dir}/.venv")
        mountpoint = self.params.get("mountpoint", "/")
        enable = self.params.get("enable", True)

        if not init_system:
            init_system = self._detect_init(mountpoint)

        root = Path(mountpoint)
        ctx = {"user": user, "install_dir": install_dir, "venv": venv}

        if init_system == "systemd":
            return self._install_systemd(root, ctx, enable)
        elif init_system == "openrc":
            return self._install_openrc(root, ctx, enable)
        elif init_system == "sysvinit":
            return self._install_sysvinit(root, ctx, enable)
        else:
            return {"init_system": init_system, "installed": False,
                    "error": f"Unsupported init system: {init_system}"}

    def _install_systemd(self, root: Path, ctx: dict, enable: bool) -> dict:
        unit_path = root / "etc/systemd/system/fsdeploy.service"
        unit_path.parent.mkdir(parents=True, exist_ok=True)
        unit_path.write_text(SYSTEMD_UNIT.format(**ctx))

        if enable and str(root) == "/":
            self.run_cmd("systemctl daemon-reload", sudo=True, check=False)
            self.run_cmd("systemctl enable fsdeploy.service", sudo=True, check=False)
        elif enable:
            self.run_cmd(
                f"chroot {root} systemctl enable fsdeploy.service",
                sudo=True, check=False,
            )

        return {"init_system": "systemd", "path": str(unit_path), "installed": True}

    def _install_openrc(self, root: Path, ctx: dict, enable: bool) -> dict:
        script_path = root / "etc/init.d/fsdeploy"
        script_path.parent.mkdir(parents=True, exist_ok=True)
        script_path.write_text(OPENRC_SCRIPT.format(**ctx))
        script_path.chmod(0o755)

        if enable:
            target = root if str(root) != "/" else Path("/")
            self.run_cmd(
                f"chroot {target} rc-update add fsdeploy default",
                sudo=True, check=False,
            )

        return {"init_system": "openrc", "path": str(script_path), "installed": True}

    def _install_sysvinit(self, root: Path, ctx: dict, enable: bool) -> dict:
        script_path = root / "etc/init.d/fsdeploy"
        script_path.parent.mkdir(parents=True, exist_ok=True)
        script_path.write_text(SYSVINIT_SCRIPT.format(**ctx))
        script_path.chmod(0o755)

        if enable:
            self.run_cmd(
                f"chroot {root} update-rc.d fsdeploy defaults",
                sudo=True, check=False,
            )

        return {"init_system": "sysvinit", "path": str(script_path), "installed": True}

    def _detect_init(self, root: str) -> str:
        r = Path(root)
        if (r / "run/systemd/system").is_dir() or (r / "usr/lib/systemd/systemd").exists():
            return "systemd"
        if (r / "sbin/openrc").exists() or (r / "usr/sbin/openrc").exists():
            return "openrc"
        if (r / "etc/init.d").is_dir():
            return "sysvinit"
        return "unknown"
