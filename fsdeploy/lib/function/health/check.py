import shutil
import subprocess
import sys

from fsdeploy.lib.scheduler.model.task import Task


class HealthCheckTask(Task):
    """
    Vérifie les prérequis du système pour fsdeploy.
    """

    def run(self):
        checks = []
        all_ok = True

        # 1. Vérification des binaires ZFS
        for binary in ("zpool", "zfs"):
            ok, msg = self._check_binary(binary)
            checks.append({"check": f"binary.{binary}", "ok": ok, "message": msg})
            if not ok:
                all_ok = False

        # 2. Vérification des permissions sudo pour zpool list
        sudo_ok, sudo_msg = self._check_sudo_zpool()
        checks.append({"check": "sudo.zpool", "ok": sudo_ok, "message": sudo_msg})
        if not sudo_ok:
            all_ok = False

        # 3. Espace disque sur /
        disk_ok, disk_msg = self._check_disk_space()
        checks.append({"check": "disk.root", "ok": disk_ok, "message": disk_msg})
        if not disk_ok:
            all_ok = False

        # 4. Version de Python
        py_ok, py_msg = self._check_python_version()
        checks.append({"check": "python.version", "ok": py_ok, "message": py_msg})
        if not py_ok:
            all_ok = False

        result = {
            "checks": checks,
            "all_ok": all_ok
        }
        self.log_event("health.check.completed", result=result)
        return result

    def _check_binary(self, name: str) -> tuple[bool, str]:
        """Retourne (ok, message) pour la présence du binaire."""
        path = shutil.which(name)
        if path is None:
            return False, f"{name} non trouvé dans PATH"
        return True, f"{name} trouvé : {path}"

    def _check_sudo_zpool(self) -> tuple[bool, str]:
        """Vérifie que `sudo -n zpool list` fonctionne."""
        try:
            proc = subprocess.run(
                ["sudo", "-n", "zpool", "list"],
                capture_output=True,
                timeout=5,
            )
            if proc.returncode == 0:
                return True, "sudo zpool list réussi"
            else:
                return False, f"sudo zpool list échoue (code {proc.returncode}) : {proc.stderr.decode().strip()}"
        except Exception as e:
            return False, f"Exception lors de sudo zpool list : {e}"

    def _check_disk_space(self, min_mb: int = 100) -> tuple[bool, str]:
        """Vérifie qu'il reste au moins min_mb mégaoctets sur /."""
        try:
            usage = shutil.disk_usage("/")
            free_mb = usage.free / (1024 * 1024)
            if free_mb >= min_mb:
                return True, f"{free_mb:.1f} MB libres sur / (minimum {min_mb} MB)"
            else:
                return False, f"seulement {free_mb:.1f} MB libres sur / (minimum {min_mb} MB)"
        except Exception as e:
            return False, f"Impossible de vérifier l'espace disque : {e}"

    def _check_python_version(self, min_version=(3, 10)) -> tuple[bool, str]:
        """Vérifie la version de Python."""
        current = sys.version_info[:2]
        if current >= min_version:
            return True, f"Python {current[0]}.{current[1]} (>= {min_version[0]}.{min_version[1]})"
        else:
            return False, f"Python {current[0]}.{current[1]} inférieur à {min_version[0]}.{min_version[1]}"
