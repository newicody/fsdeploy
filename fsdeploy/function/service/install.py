"""
fsdeploy.function.service.install
==================================
Installation de services pour différents systèmes d'init.

Supporte :
  - systemd (Debian/Ubuntu modernes)
  - openrc (Alpine, Gentoo)
  - sysvinit (ancien Debian)
  - upstart (ancien Ubuntu)

Principe : un seul service installé, le scheduler Python gère tout le reste.
"""

import os
import stat
from pathlib import Path
from typing import Any, Optional

from scheduler.model.task import Task
from scheduler.model.resource import Resource
from scheduler.model.lock import Lock
from scheduler.security.decorator import security


def _detect_init_system() -> str:
    """Détecte le système d'init actif."""
    # systemd
    if Path("/run/systemd/system").is_dir():
        return "systemd"
    
    # openrc
    if Path("/sbin/openrc").exists() or Path("/run/openrc").is_dir():
        return "openrc"
    
    # upstart
    if Path("/sbin/initctl").exists():
        try:
            import subprocess
            r = subprocess.run(
                ["/sbin/initctl", "--version"],
                capture_output=True, text=True
            )
            if "upstart" in r.stdout.lower():
                return "upstart"
        except Exception:
            pass
    
    # sysvinit fallback
    if Path("/etc/init.d").is_dir():
        return "sysvinit"
    
    return "unknown"


# ─── Templates de service ─────────────────────────────────────────────────────

SYSTEMD_UNIT = """\
[Unit]
Description=fsdeploy - ZFS Boot Manager
After=network.target zfs.target
Wants=zfs.target

[Service]
Type=simple
ExecStart={venv}/bin/python3 -m fsdeploy --daemon
ExecReload=/bin/kill -HUP $MAINPID
Restart=on-failure
RestartSec=5
User={user}
Group={group}
Environment=FSDEPLOY_INSTALL_DIR={install_dir}
WorkingDirectory={install_dir}

# Sécurité
NoNewPrivileges=false
ProtectSystem=strict
ReadWritePaths=/mnt /boot /var/log/fsdeploy /run/fsdeploy.sock
PrivateTmp=true

[Install]
WantedBy=multi-user.target
"""

OPENRC_SCRIPT = """\
#!/sbin/openrc-run
# fsdeploy - ZFS Boot Manager

name="fsdeploy"
description="fsdeploy ZFS Boot Manager"

command="{venv}/bin/python3"
command_args="-m fsdeploy --daemon"
command_user="{user}:{group}"
command_background=true
pidfile="/run/fsdeploy.pid"

directory="{install_dir}"

depend() {{
    need net
    after zfs
}}

start_pre() {{
    export FSDEPLOY_INSTALL_DIR="{install_dir}"
}}
"""

SYSVINIT_SCRIPT = """\
#!/bin/sh
### BEGIN INIT INFO
# Provides:          fsdeploy
# Required-Start:    $remote_fs $syslog $network
# Required-Stop:     $remote_fs $syslog
# Default-Start:     2 3 4 5
# Default-Stop:      0 1 6
# Short-Description: fsdeploy ZFS Boot Manager
# Description:       Manages ZFS boot configuration and streaming
### END INIT INFO

NAME=fsdeploy
DAEMON={venv}/bin/python3
DAEMON_ARGS="-m fsdeploy --daemon"
PIDFILE=/run/fsdeploy.pid
USER={user}
GROUP={group}
WORKDIR={install_dir}

export FSDEPLOY_INSTALL_DIR="{install_dir}"

case "$1" in
    start)
        echo "Starting $NAME..."
        start-stop-daemon --start --quiet --background \\
            --make-pidfile --pidfile $PIDFILE \\
            --chuid $USER:$GROUP --chdir $WORKDIR \\
            --exec $DAEMON -- $DAEMON_ARGS
        ;;
    stop)
        echo "Stopping $NAME..."
        start-stop-daemon --stop --quiet --pidfile $PIDFILE
        rm -f $PIDFILE
        ;;
    restart)
        $0 stop
        sleep 1
        $0 start
        ;;
    status)
        if [ -f $PIDFILE ] && kill -0 $(cat $PIDFILE) 2>/dev/null; then
            echo "$NAME is running (PID $(cat $PIDFILE))"
        else
            echo "$NAME is not running"
            exit 1
        fi
        ;;
    *)
        echo "Usage: $0 {{start|stop|restart|status}}"
        exit 1
        ;;
esac
"""

UPSTART_CONF = """\
# fsdeploy - ZFS Boot Manager

description "fsdeploy ZFS Boot Manager"

start on (filesystem and net-device-up IFACE!=lo)
stop on runlevel [!2345]

respawn
respawn limit 5 60

setuid {user}
setgid {group}
chdir {install_dir}

env FSDEPLOY_INSTALL_DIR={install_dir}

exec {venv}/bin/python3 -m fsdeploy --daemon
"""


@security.service.install(require_root=True)
class ServiceInstallTask(Task):
    """
    Installe le service fsdeploy pour le système d'init détecté.
    
    Params:
      - init_system: "systemd" | "openrc" | "sysvinit" | "upstart" | "auto"
      - user: utilisateur du service
      - group: groupe du service
      - install_dir: répertoire d'installation
      - venv: chemin du virtualenv
      - enable: activer au démarrage
    """

    def required_locks(self):
        return [Lock("service.fsdeploy", owner_id=str(self.id), exclusive=True)]

    def run(self) -> dict[str, Any]:
        init_system = self.params.get("init_system", "auto")
        user = self.params.get("user", "root")
        group = self.params.get("group", "fsdeploy")
        install_dir = self.params.get("install_dir", "/opt/fsdeploy")
        venv = self.params.get("venv", f"{install_dir}/.venv")
        enable = self.params.get("enable", True)

        # Auto-détection
        if init_system == "auto":
            init_system = _detect_init_system()

        results = {
            "init_system": init_system,
            "installed": False,
            "enabled": False,
            "service_path": "",
        }

        # Paramètres de template
        params = {
            "user": user,
            "group": group,
            "install_dir": install_dir,
            "venv": venv,
        }

        if init_system == "systemd":
            results.update(self._install_systemd(params, enable))
        elif init_system == "openrc":
            results.update(self._install_openrc(params, enable))
        elif init_system == "sysvinit":
            results.update(self._install_sysvinit(params, enable))
        elif init_system == "upstart":
            results.update(self._install_upstart(params, enable))
        else:
            raise ValueError(f"Unknown init system: {init_system}")

        return results

    def _install_systemd(self, params: dict, enable: bool) -> dict:
        """Installe pour systemd."""
        unit_path = Path("/etc/systemd/system/fsdeploy.service")
        content = SYSTEMD_UNIT.format(**params)
        unit_path.write_text(content)

        self.run_cmd("systemctl daemon-reload", sudo=True)

        if enable:
            self.run_cmd("systemctl enable fsdeploy.service", sudo=True)

        return {
            "installed": True,
            "enabled": enable,
            "service_path": str(unit_path),
            "start_cmd": "systemctl start fsdeploy",
        }

    def _install_openrc(self, params: dict, enable: bool) -> dict:
        """Installe pour openrc."""
        script_path = Path("/etc/init.d/fsdeploy")
        content = OPENRC_SCRIPT.format(**params)
        script_path.write_text(content)
        script_path.chmod(script_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

        if enable:
            self.run_cmd("rc-update add fsdeploy default", sudo=True)

        return {
            "installed": True,
            "enabled": enable,
            "service_path": str(script_path),
            "start_cmd": "rc-service fsdeploy start",
        }

    def _install_sysvinit(self, params: dict, enable: bool) -> dict:
        """Installe pour sysvinit."""
        script_path = Path("/etc/init.d/fsdeploy")
        content = SYSVINIT_SCRIPT.format(**params)
        script_path.write_text(content)
        script_path.chmod(script_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

        if enable:
            self.run_cmd("update-rc.d fsdeploy defaults", sudo=True)

        return {
            "installed": True,
            "enabled": enable,
            "service_path": str(script_path),
            "start_cmd": "/etc/init.d/fsdeploy start",
        }

    def _install_upstart(self, params: dict, enable: bool) -> dict:
        """Installe pour upstart."""
        conf_path = Path("/etc/init/fsdeploy.conf")
        content = UPSTART_CONF.format(**params)
        conf_path.write_text(content)

        return {
            "installed": True,
            "enabled": enable,  # upstart auto-enable si fichier présent
            "service_path": str(conf_path),
            "start_cmd": "start fsdeploy",
        }


@security.service.uninstall(require_root=True)
class ServiceUninstallTask(Task):
    """Désinstalle le service fsdeploy."""

    def required_locks(self):
        return [Lock("service.fsdeploy", owner_id=str(self.id), exclusive=True)]

    def run(self) -> dict[str, Any]:
        init_system = self.params.get("init_system", "auto")

        if init_system == "auto":
            init_system = _detect_init_system()

        results = {
            "init_system": init_system,
            "uninstalled": False,
        }

        if init_system == "systemd":
            self.run_cmd("systemctl stop fsdeploy.service", sudo=True, check=False)
            self.run_cmd("systemctl disable fsdeploy.service", sudo=True, check=False)
            Path("/etc/systemd/system/fsdeploy.service").unlink(missing_ok=True)
            self.run_cmd("systemctl daemon-reload", sudo=True)
        elif init_system == "openrc":
            self.run_cmd("rc-service fsdeploy stop", sudo=True, check=False)
            self.run_cmd("rc-update del fsdeploy", sudo=True, check=False)
            Path("/etc/init.d/fsdeploy").unlink(missing_ok=True)
        elif init_system == "sysvinit":
            self.run_cmd("/etc/init.d/fsdeploy stop", sudo=True, check=False)
            self.run_cmd("update-rc.d fsdeploy remove", sudo=True, check=False)
            Path("/etc/init.d/fsdeploy").unlink(missing_ok=True)
        elif init_system == "upstart":
            self.run_cmd("stop fsdeploy", sudo=True, check=False)
            Path("/etc/init/fsdeploy.conf").unlink(missing_ok=True)

        results["uninstalled"] = True
        return results


@security.service.status
class ServiceStatusTask(Task):
    """Vérifie l'état du service fsdeploy."""

    def run(self) -> dict[str, Any]:
        init_system = self.params.get("init_system", "auto")

        if init_system == "auto":
            init_system = _detect_init_system()

        results = {
            "init_system": init_system,
            "installed": False,
            "running": False,
            "enabled": False,
        }

        if init_system == "systemd":
            # Vérifie si installé
            results["installed"] = Path("/etc/systemd/system/fsdeploy.service").exists()

            # Vérifie si actif
            r = self.run_cmd("systemctl is-active fsdeploy.service", check=False)
            results["running"] = r.stdout.strip() == "active"

            # Vérifie si enabled
            r = self.run_cmd("systemctl is-enabled fsdeploy.service", check=False)
            results["enabled"] = r.stdout.strip() == "enabled"

        elif init_system == "openrc":
            results["installed"] = Path("/etc/init.d/fsdeploy").exists()
            r = self.run_cmd("rc-service fsdeploy status", check=False)
            results["running"] = r.returncode == 0

        elif init_system == "sysvinit":
            results["installed"] = Path("/etc/init.d/fsdeploy").exists()
            r = self.run_cmd("/etc/init.d/fsdeploy status", check=False)
            results["running"] = r.returncode == 0

        elif init_system == "upstart":
            results["installed"] = Path("/etc/init/fsdeploy.conf").exists()
            r = self.run_cmd("status fsdeploy", check=False)
            results["running"] = "running" in r.stdout.lower()

        return results


# Re-exports
__all__ = ["ServiceInstallTask", "ServiceUninstallTask", "ServiceStatusTask"]
