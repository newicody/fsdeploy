"""
Runner pour l'exécution des tâches avec gestion du sudo et du chroot.
Implémente la logique d'exécution multi-environnements selon add.md.
"""

import subprocess
import threading
import time
import os
from pathlib import Path
from typing import Dict, Any, Optional, Callable, Union
import uuid
import logging
import shlex


class TaskRunner:
    """Gère l'exécution des tâches avec isolation chroot et authentification sudo."""
    
    def __init__(self, bridge=None, config_mapper=None):
        self.bridge = bridge
        self.config_mapper = config_mapper
        self.log = logging.getLogger(__name__)
        
        # Stockage des tâches en attente d'authentification
        self.pending_auth_tasks: Dict[str, Dict] = {}
        self.auth_lock = threading.Lock()
        self.sudo_password: Optional[str] = None
        
        # Cage chroot par défaut
        self.default_chroot = "/opt/fsdeploy/bootstrap"
        self.active_chroots: Dict[str, bool] = {}
    
    def execute_task(self, task_id: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Exécute une tâche à partir d'une section de configuration.
        
        Args:
            task_id: ID de la tâche/section
            params: Paramètres supplémentaires
            
        Returns:
            Résultat de l'exécution
        """
        if not self.config_mapper:
            return {"success": False, "error": "ConfigMapper non initialisé"}
        
        # Obtenir la section de configuration
        config_section = self.config_mapper.get_section(task_id)
        if not config_section:
            return {"success": False, "error": f"Section {task_id} non trouvée"}
        
        section_data = config_section.get("data", {})
        params = params or {}
        
        # Déterminer le mode d'exécution
        sudo_required = section_data.get("sudo", False) or params.get("sudo", False)
        environment = section_data.get("environment", "host")
        command = section_data.get("command", "")
        args = section_data.get("args", [])
        
        if not command:
            return {"success": False, "error": "Commande non spécifiée"}
        
        # Construire la commande complète
        full_command = self._build_command(command, args, params)
        
        # Gérer l'authentification sudo
        if sudo_required and not self.sudo_password:
            return self._request_sudo_auth(task_id, full_command, environment, params)
        
        # Exécuter la commande
        return self._execute_command(full_command, environment, sudo_required)
    
    def _build_command(self, command: str, args: list, params: Dict[str, Any]) -> str:
        """Construit la commande complète avec arguments et paramètres."""
        # Ajouter les arguments de base
        if args:
            args_str = " ".join(shlex.quote(str(arg)) for arg in args)
            full_cmd = f"{command} {args_str}"
        else:
            full_cmd = command
        
        # Remplacer les paramètres dans la commande
        for key, value in params.items():
            if key not in ["sudo", "environment", "callback"]:
                placeholder = f"{{{key}}}"
                if placeholder in full_cmd:
                    full_cmd = full_cmd.replace(placeholder, shlex.quote(str(value)))
        
        return full_cmd
    
    def _request_sudo_auth(self, task_id: str, command: str, 
                          environment: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Demande l'authentification sudo via le bridge.
        
        Returns:
            Statut d'attente
        """
        # Générer un ID de ticket pour le suivi
        auth_ticket_id = f"auth-{uuid.uuid4().hex[:8]}"
        
        # Stocker la tâche en attente
        with self.auth_lock:
            self.pending_auth_tasks[auth_ticket_id] = {
                "task_id": task_id,
                "command": command,
                "environment": environment,
                "params": params,
                "timestamp": time.time()
            }
        
        # Émettre la demande via le bridge
        if self.bridge:
            self.bridge.emit(
                "auth.sudo_request",
                section_id=task_id,
                action=f"Exécution de {task_id}",
                auth_ticket_id=auth_ticket_id
            )
        
        return {
            "success": False,
            "status": "waiting_for_auth",
            "auth_ticket_id": auth_ticket_id,
            "message": "Authentification sudo requise"
        }
    
    def set_sudo_password(self, password: str, auth_ticket_id: Optional[str] = None):
        """
        Définit le mot de passe sudo et reprend les tâches en attente.
        
        Args:
            password: Mot de passe sudo
            auth_ticket_id: ID spécifique du ticket d'authentification
        """
        self.sudo_password = password
        
        # Reprendre les tâches en attente
        with self.auth_lock:
            if auth_ticket_id:
                # Reprendre une tâche spécifique
                if auth_ticket_id in self.pending_auth_tasks:
                    task_info = self.pending_auth_tasks.pop(auth_ticket_id)
                    self._resume_task(task_info, password)
            else:
                # Reprendre toutes les tâches
                for ticket_id, task_info in list(self.pending_auth_tasks.items()):
                    self._resume_task(task_info, password)
                    self.pending_auth_tasks.pop(ticket_id, None)
    
    def _resume_task(self, task_info: Dict[str, Any], password: str):
        """Reprend l'exécution d'une tâche mise en attente."""
        # Dans une implémentation réelle, nous devrions notifier le bridge
        # Pour l'instant, nous exécutons simplement la tâche
        result = self._execute_command(
            task_info["command"],
            task_info["environment"],
            True,  # sudo_required
            password
        )
        
        # Notifier via le bridge si disponible
        if self.bridge and "callback" in task_info.get("params", {}):
            callback = task_info["params"]["callback"]
            if callable(callback):
                callback(result)
    
    def _execute_command(self, command: str, environment: str, 
                        sudo_required: bool, password: Optional[str] = None) -> Dict[str, Any]:
        """
        Exécute une commande dans l'environnement spécifié.
        
        Args:
            command: Commande à exécuter
            environment: Environnement (host, chroot)
            sudo_required: Si l'exécution nécessite sudo
            password: Mot de passe sudo si nécessaire
            
        Returns:
            Résultat de l'exécution
        """
        # Préparer la commande avec sudo si nécessaire
        if sudo_required:
            if password:
                # Utiliser sudo avec injection du mot de passe
                full_command = f"echo '{password}' | sudo -S -k {command}"
                use_shell = True
            else:
                # Utiliser sudo sans mot de passe (suppose NOPASSWD configuré)
                full_command = f"sudo {command}"
                use_shell = True
        else:
            full_command = command
            use_shell = True if "|" in command or "&&" in command else False
        
        # Exécuter dans l'environnement approprié
        if environment == "chroot":
            return self._execute_in_chroot(full_command, use_shell)
        else:
            return self._execute_in_host(full_command, use_shell)
    
    def _execute_in_host(self, command: str, use_shell: bool) -> Dict[str, Any]:
        """Exécute une commande sur l'hôte."""
        try:
            result = subprocess.run(
                command,
                shell=use_shell,
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes timeout
            )
            
            return {
                "success": result.returncode == 0,
                "returncode": result.returncode,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
                "command": command
            }
            
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Timeout expiré",
                "command": command
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "command": command
            }
    
    def _execute_in_chroot(self, command: str, use_shell: bool) -> Dict[str, Any]:
        """Exécute une commande dans un environnement chroot."""
        chroot_path = self.default_chroot
        
        # Vérifier que le chroot existe
        if not Path(chroot_path).exists():
            return {
                "success": False,
                "error": f"Chroot path n'existe pas: {chroot_path}",
                "command": command
            }
        
        try:
            # Monter les systèmes de fichiers nécessaires
            self._mount_chroot_deps(chroot_path)
            
            # Préparer la commande chroot
            chroot_command = f"chroot {chroot_path} {command}"
            
            # Exécuter
            result = subprocess.run(
                chroot_command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            return {
                "success": result.returncode == 0,
                "returncode": result.returncode,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
                "command": chroot_command
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "command": command
            }
        finally:
            # Nettoyer les montages
            self._cleanup_chroot(chroot_path)
    
    def _mount_chroot_deps(self, chroot_path: str):
        """Monte les systèmes de fichiers nécessaires dans le chroot."""
        mounts = [
            ("/dev", f"{chroot_path}/dev"),
            ("/proc", f"{chroot_path}/proc"),
            ("/sys", f"{chroot_path}/sys"),
        ]
        
        for src, dst in mounts:
            if Path(src).exists():
                # Créer le point de montage s'il n'existe pas
                Path(dst).mkdir(parents=True, exist_ok=True)
                
                # Monter
                subprocess.run(
                    ["mount", "--bind", src, dst],
                    capture_output=True,
                    check=False
                )
        
        # Marquer comme actif
        self.active_chroots[chroot_path] = True
    
    def _cleanup_chroot(self, chroot_path: str):
        """Nettoie les montages du chroot."""
        if chroot_path in self.active_chroots:
            mounts = [
                f"{chroot_path}/sys",
                f"{chroot_path}/proc",
                f"{chroot_path}/dev",
            ]
            
            for mount_point in mounts:
                if Path(mount_point).exists():
                    subprocess.run(
                        ["umount", mount_point],
                        capture_output=True,
                        check=False
                    )
            
            # Retirer de la liste active
            self.active_chroots.pop(chroot_path, None)
