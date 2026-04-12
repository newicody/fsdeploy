"""
fsdeploy.function.live.setup
=============================
Configuration de l'environnement Debian Live Trixie.

Opérations :
  1. Modifier les sources APT (contrib, non-free, backports)
  2. Installer les paquets système (zfsutils, linux-headers, git, etc.)
  3. Attendre DKMS ZFS si nécessaire
  4. Créer les groupes et permissions
  5. Préparer le virtualenv Python
"""

import os
import time
from pathlib import Path
from typing import Any

from scheduler.model.task import Task, CommandResult
from scheduler.model.resource import Resource
from scheduler.model.lock import Lock
from scheduler.security.decorator import security


DEBIAN_PACKAGES = [
    "linux-headers-amd64",
    "zfsutils-linux",
    "zfs-dkms",
    "git",
    "squashfs-tools",
    "dracut",
    "dracut-core",
    "efibootmgr",
    "dosfstools",
    "gdisk",
    "ffmpeg",
    "zstd",
    "xz-utils",
    "lz4",
    "pv",
    "python3",
    "python3-venv",
]


@security.live.setup(require_root=True)
class LiveSetupTask(Task):
    """
    Configure l'environnement Debian Live pour fsdeploy.
    """

    def required_resources(self):
        return [Resource("system.apt"), Resource("system.groups")]

    def required_locks(self):
        return [Lock("system.apt", owner_id=str(self.id))]

    def run(self) -> dict[str, Any]:
        results = {
            "sources_modified": False,
            "packages_installed": [],
            "dkms_ready": False,
            "groups_created": [],
            "venv_ready": False,
        }

        # 1. Sources APT
        results["sources_modified"] = self._setup_apt_sources()

        # 2. apt update + install
        self.run_cmd("apt-get update -qq", sudo=True)
        results["packages_installed"] = self._install_packages()

        # 3. DKMS
        results["dkms_ready"] = self._wait_dkms()

        # 4. Groupes
        results["groups_created"] = self._setup_groups()

        # 5. Venv
        results["venv_ready"] = self._setup_venv()

        return results

    def _setup_apt_sources(self) -> bool:
        """Ajoute contrib, non-free, non-free-firmware et backports."""
        sources_file = Path("/etc/apt/sources.list")
        if not sources_file.exists():
            sources_dir = Path("/etc/apt/sources.list.d")
            # Chercher le fichier principal
            candidates = list(sources_dir.glob("*.list")) + list(sources_dir.glob("*.sources"))
            if not candidates:
                return False
            sources_file = candidates[0]

        content = sources_file.read_text()
        modified = False

        # Ajouter les composants manquants
        for component in ("contrib", "non-free", "non-free-firmware"):
            if component not in content:
                content = content.replace(
                    "main", f"main {component}", 1
                )
                modified = True

        if modified:
            sources_file.write_text(content)

        # Backports
        backports = Path("/etc/apt/sources.list.d/backports.list")
        if not backports.exists():
            backports.write_text(
                "deb http://deb.debian.org/debian trixie-backports main contrib non-free non-free-firmware\n"
            )
            modified = True

        return modified

    def _install_packages(self) -> list[str]:
        """Installe les paquets nécessaires."""
        packages = DEBIAN_PACKAGES.copy()
        # Remplacer linux-headers-amd64 par linux-headers-$(uname -r)
        result = self.run_cmd("uname -r", check=False)
        if result.success and result.stdout.strip():
            kernel_release = result.stdout.strip()
            target_header = f"linux-headers-{kernel_release}"
            for i, pkg in enumerate(packages):
                if pkg == "linux-headers-amd64":
                    packages[i] = target_header
                    break
        # installer
        installed = []
        pkg_str = " ".join(packages)
        result = self.run_cmd(
            f"apt-get install -y -qq {pkg_str}",
            sudo=True, check=False, timeout=600,
        )
        if result.success:
            installed = packages
        else:
            for pkg in packages:
                r = self.run_cmd(
                    f"apt-get install -y -qq {pkg}",
                    sudo=True, check=False, timeout=120,
                )
                if r.success:
                    installed.append(pkg)
        return installed

    def _wait_dkms(self, timeout: int = 180) -> bool:
        """Attend que DKMS compile les modules ZFS."""
        start = time.monotonic()
        while time.monotonic() - start < timeout:
            result = self.run_cmd(
                "dkms status -m zfs",
                sudo=True, check=False,
            )
            if "installed" in result.stdout.lower():
                # Charger les modules
                self.run_cmd("modprobe zfs", sudo=True, check=False)
                return True
            time.sleep(5)
        return False

    def _setup_groups(self) -> list[str]:
        """Crée les groupes nécessaires."""
        created = []
        for group in ("fsdeploy", "disk"):
            result = self.run_cmd(
                f"groupadd -f {group}",
                sudo=True, check=False,
            )
            if result.success:
                created.append(group)

        # Ajouter l'utilisateur aux groupes
        user = os.environ.get("FSDEPLOY_USER", os.environ.get("SUDO_USER", ""))
        if user:
            groups = "fsdeploy,disk,sudo,video"
            self.run_cmd(
                f"usermod -aG {groups} {user}",
                sudo=True, check=False,
            )
        return created

    def _setup_venv(self) -> bool:
        """Crée le virtualenv Python."""
        install_dir = os.environ.get("FSDEPLOY_INSTALL_DIR", "/opt/fsdeploy")
        venv_dir = f"{install_dir}/.venv"

        if Path(f"{venv_dir}/bin/python3").exists():
            return True

        result = self.run_cmd(
            f"python3 -m venv --system-site-packages {venv_dir}",
            check=False,
        )
        if not result.success:
            return False

        req_file = f"{install_dir}/requirements.txt"
        if Path(req_file).exists():
            self.run_cmd(
                f"{venv_dir}/bin/pip install --quiet --upgrade -r {req_file}",
                check=False, timeout=300,
            )
        return True
