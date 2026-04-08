"""
Détection des noyaux mainline et des modules externes.
"""
import subprocess
import re
from pathlib import Path
from typing import Dict, Any, List, Optional

from fsdeploy.lib.scheduler.model.task import Task


class KernelMainlineDetectTask(Task):
    """
    Détecte les noyaux mainline (installés via packages ou compilés manuellement)
    et les modules externes associés.
    """

    def execute(self) -> Dict[str, Any]:
        self.log_event("kernel.mainline.detect.started", {"params": self.params})

        scan_paths = self.params.get("scan_paths", ["/usr/src", "/lib/modules"])
        detect_packages = self.params.get("detect_packages", True)

        result = {
            "kernels": [],
            "external_modules": [],
            "errors": [],
        }

        # Détection des noyaux via packages (dpkg, pacman, rpm)
        if detect_packages:
            pkgs = self._detect_kernel_packages()
            result["kernels"].extend(pkgs)

        # Détection des noyaux dans /usr/src (sources)
        src_kernels = self._scan_src_kernels(scan_paths)
        result["kernels"].extend(src_kernels)

        # Détection des modules externes (hors arborescence standard)
        ext_mods = self._scan_external_modules(scan_paths)
        result["external_modules"] = ext_mods

        self.log_event("kernel.mainline.detect.completed", result)
        return result

    def _detect_kernel_packages(self) -> List[Dict[str, Any]]:
        """Retourne la liste des noyaux installés via le gestionnaire de packages."""
        kernels = []
        # Détection dpkg (Debian/Ubuntu)
        try:
            out = subprocess.check_output(
                ["dpkg", "-l", "linux-image-*"],
                stderr=subprocess.DEVNULL,
                text=True,
            )
            for line in out.splitlines():
                if line.startswith("ii"):
                    parts = line.split()
                    if len(parts) >= 3:
                        pkg = parts[1]
                        version = parts[2]
                        kernels.append({
                            "package": pkg,
                            "version": version,
                            "type": "deb",
                        })
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

        # Détection pacman (Arch)
        try:
            out = subprocess.check_output(
                ["pacman", "-Q", "linux", "linux-lts", "linux-zen", "linux-hardened"],
                stderr=subprocess.DEVNULL,
                text=True,
            )
            for line in out.splitlines():
                pkg, version = line.split()
                kernels.append({
                    "package": pkg,
                    "version": version,
                    "type": "pacman",
                })
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

        # Détection rpm (Fedora/RHEL)
        try:
            out = subprocess.check_output(
                ["rpm", "-qa", "kernel-*"],
                stderr=subprocess.DEVNULL,
                text=True,
            )
            for pkg in out.splitlines():
                # kernel-5.14.0-70.13.1.el9_0.x86_64
                if pkg.startswith("kernel-") and not pkg.startswith("kernel-headers"):
                    # Extraire version approximative
                    version = pkg.replace("kernel-", "")
                    kernels.append({
                        "package": pkg,
                        "version": version,
                        "type": "rpm",
                    })
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

        return kernels

    def _scan_src_kernels(self, scan_paths: List[str]) -> List[Dict[str, Any]]:
        """Recherche les répertoires de sources de noyaux."""
        src_kernels = []
        for base in scan_paths:
            bp = Path(base)
            if not bp.exists():
                continue
            # Chercher les répertoires nommés linux-* ou avec un Makefile
            for d in bp.iterdir():
                if d.is_dir() and d.name.startswith("linux-"):
                    makefile = d / "Makefile"
                    if makefile.exists():
                        # Lire la version depuis le Makefile
                        version = self._extract_kernel_version(makefile)
                        src_kernels.append({
                            "path": str(d),
                            "version": version,
                            "type": "source",
                        })
        return src_kernels

    def _extract_kernel_version(self, makefile_path: Path) -> str:
        """Extrait la version du noyau depuis le Makefile."""
        try:
            content = makefile_path.read_text()
            # Recherche de VERSION = x, PATCHLEVEL = y, SUBLEVEL = z
            version = None
            patchlevel = None
            sublevel = None
            for line in content.splitlines():
                if line.startswith("VERSION"):
                    version = line.split("=")[1].strip()
                elif line.startswith("PATCHLEVEL"):
                    patchlevel = line.split("=")[1].strip()
                elif line.startswith("SUBLEVEL"):
                    sublevel = line.split("=")[1].strip()
            if version is not None and patchlevel is not None:
                if sublevel is not None:
                    return f"{version}.{patchlevel}.{sublevel}"
                else:
                    return f"{version}.{patchlevel}"
        except Exception:
            pass
        return "unknown"

    def _scan_external_modules(self, scan_paths: List[str]) -> List[Dict[str, Any]]:
        """Recherche les modules compilés hors de l'arborescence standard."""
        modules = []
        for base in scan_paths:
            bp = Path(base)
            if not bp.exists():
                continue
            # Chercher les fichiers .ko dans des sous-répertoires non standard
            for ko in bp.rglob("*.ko"):
                # Exclure /lib/modules/<version>/kernel/...
                if "/lib/modules/" in str(ko) and "/kernel/" in str(ko):
                    continue
                # Exclure /usr/lib/modules/...
                if "/usr/lib/modules/" in str(ko):
                    continue
                modules.append({
                    "path": str(ko),
                    "size": ko.stat().st_size,
                })
        return modules
