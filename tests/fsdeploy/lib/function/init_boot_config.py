"""
Configuration fine des paramètres de boot pour le système d'initialisation détecté.
"""
import subprocess
import shutil
from pathlib import Path
from typing import Dict, Any, List

from fsdeploy.lib.scheduler.model.task import Task


class InitBootConfigTask(Task):
    """
    Configure les paramètres de boot (par exemple, options de ligne de commande du noyau,
    timeouts, thèmes) selon le système d'initialisation détecté.
    """

    def execute(self) -> Dict[str, Any]:
        self.log_event("init.boot.config.started", {"params": self.params})

        target_root = self.params.get("target_root", "/")
        init_system = self.params.get("init_system", "")
        boot_params = self.params.get("boot_params", {})
        dry_run = self.params.get("dry_run", False)

        result = {
            "target_root": target_root,
            "init_system": init_system,
            "boot_params_applied": [],
            "errors": [],
            "dry_run": dry_run,
        }

        # Mapping des systèmes d'init vers les méthodes de configuration
        config_handlers = {
            "systemd": self._configure_systemd_boot,
            "grub": self._configure_grub,
            "openrc": self._configure_openrc,
            "upstart": self._configure_upstart,
            "sysvinit": self._configure_sysvinit,
        }

        handler = config_handlers.get(init_system)
        if handler is None:
            result["errors"].append(
                f"Système d'init '{init_system}' non pris en charge pour la configuration boot."
            )
            self.log_event("init.boot.config.skipped", result)
            return result

        try:
            applied = handler(target_root, boot_params, dry_run)
            result["boot_params_applied"] = applied
        except Exception as e:
            result["errors"].append(f"Erreur lors de la configuration: {e}")

        if result["errors"]:
            self.log_event("init.boot.config.completed_with_errors", result)
        else:
            self.log_event("init.boot.config.completed", result)
        return result

    def _configure_systemd_boot(self, target_root: str, params: dict, dry_run: bool) -> List[str]:
        """Configure systemd-boot (si utilisé)."""
        applied = []
        loader_dir = Path(target_root) / "boot" / "loader"
        entries_dir = loader_dir / "entries"
        if not entries_dir.exists():
            # systemd-boot non installé
            return []
        # Modifier le fichier loader.conf
        loader_conf = loader_dir / "loader.conf"
        lines = []
        if loader_conf.exists():
            lines = loader_conf.read_text().splitlines()
        for key, value in params.get("loader", {}).items():
            # Rechercher la ligne existante
            found = False
            for i, line in enumerate(lines):
                if line.startswith(f"{key} "):
                    lines[i] = f"{key} {value}"
                    found = True
                    break
            if not found:
                lines.append(f"{key} {value}")
            applied.append(f"loader.{key}")
        if not dry_run:
            loader_conf.write_text("\n".join(lines) + "\n")
        # On pourrait aussi modifier les entrées de noyau
        return applied

    def _configure_grub(self, target_root: str, params: dict, dry_run: bool) -> List[str]:
        """Configure GRUB2."""
        applied = []
        grub_default = Path(target_root) / "etc" / "default" / "grub"
        if not grub_default.exists():
            # GRUB non installé
            return []
        content = grub_default.read_text()
        lines = content.splitlines()
        for key, value in params.get("grub", {}).items():
            # Format GRUB: GRUB_CMDLINE_LINUX_DEFAULT="..."
            prefix = f"GRUB_{key.upper()}="
            found = False
            for i, line in enumerate(lines):
                if line.startswith(prefix):
                    lines[i] = f'{prefix}"{value}"'
                    found = True
                    break
            if not found:
                lines.append(f'{prefix}"{value}"')
            applied.append(f"grub.{key}")
        if not dry_run:
            grub_default.write_text("\n".join(lines) + "\n")
            # Mettre à jour GRUB si demandé
            update_grub = params.get("update_grub", True)
            if update_grub and not dry_run:
                # Essayer grub-mkconfig ou update-grub
                if shutil.which("grub-mkconfig"):
                    subprocess.run(["grub-mkconfig", "-o", f"{target_root}/boot/grub/grub.cfg"], check=False)
                elif shutil.which("update-grub"):
                    subprocess.run(["update-grub"], check=False)
        return applied

    def _configure_openrc(self, target_root: str, params: dict, dry_run: bool) -> List[str]:
        """Configuration pour OpenRC (par exemple, kernel modules)."""
        # Peu de paramètres de boot spécifiques pour OpenRC.
        # On peut modifier /etc/conf.d/modules
        applied = []
        modules_conf = Path(target_root) / "etc" / "conf.d" / "modules"
        if modules_conf.exists():
            # Ajouter les modules demandés
            modules = params.get("modules", [])
            if modules:
                content = modules_conf.read_text()
                lines = content.splitlines()
                for mod in modules:
                    if f"modules=\"{mod}\"" not in content:
                        # Ajouter à la ligne modules="..."
                        # Simpliste: on ajoute à la fin
                        lines.append(f'modules="${{modules}} {mod}"')
                        applied.append(f"modules.{mod}")
                if not dry_run:
                    modules_conf.write_text("\n".join(lines) + "\n")
        return applied

    def _configure_upstart(self, target_root: str, params: dict, dry_run: bool) -> List[str]:
        """Configuration pour Upstart (peu de paramètres de boot)."""
        # Upstart utilise généralement GRUB pour les paramètres de boot
        return self._configure_grub(target_root, params, dry_run)

    def _configure_sysvinit(self, target_root: str, params: dict, dry_run: bool) -> List[str]:
        """Configuration pour SysVinit (peu de paramètres de boot)."""
        # SysVinit utilise généralement GRUB pour les paramètres de boot
        return self._configure_grub(target_root, params, dry_run)
