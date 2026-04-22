"""
fsdeploy.lib.scheduler.core.config_runner
===========================================
Runner pour l'exécution des sections de configuration.
Gère les modes standard, sudo_host et sudo_chroot.
"""

import subprocess
import os
import shutil
import tempfile
import logging
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)


class ConfigRunner:
    """Exécute des commandes selon les modes définis dans la configuration."""
    
    def __init__(self, config=None):
        self.config = config
        self._sudo_password = None
        self._chroot_base = "/opt/fsdeploy/bootstrap"
    
    def set_sudo_password(self, password: str):
        """Définit le mot de passe sudo pour les exécutions futures."""
        self._sudo_password = password
    
    def execute(self, section_id: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Exécute une section de configuration.
        
        Args:
            section_id: ID de la section de configuration
            params: Paramètres supplémentaires pour l'exécution
            
        Returns:
            Résultat de l'exécution
        """
        if not self.config:
            return {"success": False, "error": "Configuration non disponible"}
        
        # Récupérer la section de configuration
        section = None
        if hasattr(self.config, 'get'):
            section = self.config.get(section_id, {})
        elif isinstance(self.config, dict):
            section = self.config.get(section_id, {})
        
        if not section:
            return {"success": False, "error": f"Section '{section_id}' introuvable"}
        
        mode = section.get("mode", "standard")
        command = section.get("command", "")
        args = section.get("args", [])
        
        if params:
            # Remplacer les variables dans la commande
            for key, value in params.items():
                command = command.replace(f"${{{key}}}", str(value))
                # Remplacer aussi dans les arguments
                args = [arg.replace(f"${{{key}}}", str(value)) for arg in args]
        
        if mode == "standard":
            return self._execute_standard(command, args, section)
        elif mode == "sudo_host":
            return self._execute_sudo_host(command, args, section)
        elif mode == "sudo_chroot":
            return self._execute_sudo_chroot(command, args, section)
        else:
            return {"success": False, "error": f"Mode '{mode}' non supporté"}
    
    def _execute_standard(self, command: str, args: list, section: Dict) -> Dict[str, Any]:
        """Exécution en mode standard."""
        try:
            full_command = [command] + args
            logger.info(f"Exécution standard: {full_command}")
            
            result = subprocess.run(
                full_command,
                capture_output=True,
                text=True,
                cwd=section.get("cwd"),
                env={**os.environ, **section.get("env", {})},
                timeout=section.get("timeout", 300)
            )
            
            return {
                "success": result.returncode == 0,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "command": full_command
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Timeout expiré"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _execute_sudo_host(self, command: str, args: list, section: Dict) -> Dict[str, Any]:
        """Exécution avec privilèges sudo."""
        if not self._sudo_password:
            return {"success": False, "error": "Mot de passe sudo requis"}
        
        try:
            full_command = ["sudo", "-S", "-k"] + [command] + args
            logger.info(f"Exécution sudo_host: {full_command}")
            
            result = subprocess.run(
                full_command,
                input=self._sudo_password + "\n",
                capture_output=True,
                text=True,
                cwd=section.get("cwd"),
                env={**os.environ, **section.get("env", {})},
                timeout=section.get("timeout", 300)
            )
            
            return {
                "success": result.returncode == 0,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "command": full_command
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Timeout expiré"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _execute_sudo_chroot(self, command: str, args: list, section: Dict) -> Dict[str, Any]:
        """Exécution dans un chroot avec montages bind."""
        if not self._sudo_password:
            return {"success": False, "error": "Mot de passe sudo requis"}
        
        # Créer un répertoire temporaire pour les montages
        temp_dir = tempfile.mkdtemp(prefix="fsdeploy-chroot-")
        
        try:
            # 1. Préparer les montages bind
            mounts = section.get("bind_mounts", ["/dev", "/proc", "/sys"])
            for mount in mounts:
                mount_cmd = ["sudo", "-S", "mount", "--bind", mount, f"{self._chroot_base}{mount}"]
                subprocess.run(
                    mount_cmd, 
                    input=self._sudo_password + "\n", 
                    capture_output=True, 
                    text=True,
                    timeout=30
                )
            
            # 2. Exécuter la commande dans le chroot
            chroot_command = ["sudo", "-S", "chroot", self._chroot_base] + [command] + args
            logger.info(f"Exécution sudo_chroot: {chroot_command}")
            
            result = subprocess.run(
                chroot_command,
                input=self._sudo_password + "\n",
                capture_output=True,
                text=True,
                timeout=section.get("timeout", 300)
            )
            
            # 3. Nettoyer les montages
            for mount in reversed(mounts):
                umount_cmd = ["sudo", "-S", "umount", f"{self._chroot_base}{mount}"]
                subprocess.run(
                    umount_cmd, 
                    input=self._sudo_password + "\n", 
                    capture_output=True, 
                    text=True,
                    timeout=30
                )
            
            # 4. Nettoyer le répertoire temporaire
            shutil.rmtree(temp_dir, ignore_errors=True)
            
            return {
                "success": result.returncode == 0,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "command": chroot_command
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Timeout expiré"}
        except Exception as e:
            # Nettoyage en cas d'erreur
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except:
                pass
            return {"success": False, "error": str(e)}
