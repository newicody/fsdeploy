"""
Configuration et détection des systèmes d'init pour la cible et l'environnement live.
"""
import os
import subprocess
from pathlib import Path
from typing import Dict, Any

from fsdeploy.lib.scheduler.model.task import Task

class InitConfigDetectTask(Task):
    """Détecte et rapporte la configuration du système d'init sur la cible et le live."""

    def execute(self) -> Dict[str, Any]:
        self.log_event("init.config.detect.started", {"params": self.params})
        
        target_root = self.params.get("target_root", "/")
        live_root = self.params.get("live_root", "/run/initramfs/live")
        
        target_init = self._detect_init_system(target_root)
        live_init = self._detect_init_system(live_root)
        
        # Vérification de la présence des unités systemd, openrc, etc.
        target_units = self._list_init_units(target_root, target_init)
        live_units = self._list_init_units(live_root, live_init)
        
        result = {
            "target": {
                "root": target_root,
                "init": target_init,
                "units": target_units,
            },
            "live": {
                "root": live_root,
                "init": live_init,
                "units": live_units,
            },
        }
        self.log_event("init.config.detect.completed", result)
        return result
    
    def _detect_init_system(self, root: str) -> str:
        """Détecte le système d'init dans le répertoire racine donné."""
        # Vérifier systemd
        if (Path(root) / "usr/lib/systemd/systemd").exists() or (Path(root) / "lib/systemd/systemd").exists():
            return "systemd"
        # Vérifier openrc
        if (Path(root) / "sbin/openrc-init").exists() or (Path(root) / "etc/init.d/rc").exists():
            return "openrc"
        # Vérifier sysvinit
        if (Path(root) / "sbin/init").exists() and (Path(root) / "etc/inittab").exists():
            return "sysvinit"
        # Vérifier upstart
        if (Path(root) / "sbin/upstart").exists() or (Path(root) / "etc/init").exists():
            return "upstart"
        return "unknown"
    
    def _list_init_units(self, root: str, init: str) -> list:
        """Liste les unités ou scripts disponibles pour le système détecté."""
        units = []
        if init == "systemd":
            systemd_path = Path(root) / "etc/systemd/system"
            if systemd_path.exists():
                for f in systemd_path.iterdir():
                    if f.suffix in (".service", ".target"):
                        units.append(f.name)
        elif init == "openrc":
            initd_path = Path(root) / "etc/init.d"
            if initd_path.exists():
                for f in initd_path.iterdir():
                    if f.is_file() and os.access(f, os.X_OK):
                        units.append(f.name)
        # etc...
        return units
