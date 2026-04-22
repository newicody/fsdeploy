"""
fsdeploy.lib.scheduler.runner
==============================
Runner multi-mode pour l'exécution sécurisée des tâches.

Modes supportés :
- standard : exécution normale
- sudo : exécution avec privilèges root (tunnel sudo)
- chroot : exécution dans la cage (tunnel chroot)

Conforme à add.md 38.3.
"""

import subprocess
import threading
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
import os
import shlex

from fsdeploy.lib.log import get_logger

logger = get_logger(__name__)


@dataclass
class TaskNode:
    """Nœud de tâche validé par le Resolver."""
    command: str
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    root: bool = False
    chroot: bool = False
    working_dir: Optional[str] = None
    timeout: Optional[float] = None
    security_context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionResult:
    """Résultat d'exécution d'une tâche."""
    success: bool
    return_code: int
    stdout: str
    stderr: str
    execution_time: float
    error_message: Optional[str] = None


class MultiModeRunner:
    """
    Exécuteur multi-mode pour les tâches du scheduler.
    
    Gère trois modes d'exécution :
    1. Standard : exécution normale
    2. Sudo : exécution avec élévation de privilèges
    3. Chroot : exécution dans la cage bootstrap
    """
    
    def __init__(self, bridge=None, config=None):
        self.bridge = bridge
        self.config = config
        self.chroot_base = "/opt/fsdeploy/bootstrap"
        self._mount_points = []
        
    def execute(self, task_node: TaskNode) -> ExecutionResult:
        """
        Exécute une tâche selon son mode.
        
        Args:
            task_node: Nœud de tâche validé
            
        Returns:
            ExecutionResult: Résultat de l'exécution
        """
        start_time = time.time()
        
        # Validation de sécurité finale
        if not self._validate_security(task_node):
            return ExecutionResult(
                success=False,
                return_code=-1,
                stdout="",
                stderr="",
                execution_time=0,
                error_message="Tâche bloquée par les politiques de sécurité"
            )
        
        try:
            if task_node.chroot:
                return self._execute_chroot(task_node, start_time)
            elif task_node.root:
                return self._execute_sudo(task_node, start_time)
            else:
                return self._execute_standard(task_node, start_time)
        except Exception as e:
            return ExecutionResult(
                success=False,
                return_code=-1,
                stdout="",
                stderr=str(e),
                execution_time=time.time() - start_time,
                error_message=f"Erreur d'exécution: {e}"
            )
    
    def _execute_standard(self, task_node: TaskNode, start_time: float) -> ExecutionResult:
        """Exécution standard sans privilèges."""
        cmd = self._build_command(task_node)
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=task_node.working_dir,
                env={**os.environ, **task_node.env},
                timeout=task_node.timeout
            )
            
            return ExecutionResult(
                success=result.returncode == 0,
                return_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                execution_time=time.time() - start_time
            )
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                success=False,
                return_code=-1,
                stdout="",
                stderr="",
                execution_time=time.time() - start_time,
                error_message="Timeout expiré"
            )
    
    def _execute_sudo(self, task_node: TaskNode, start_time: float) -> ExecutionResult:
        """
        Exécution avec privilèges root via tunnel sudo.
        
        Utilise sudo -S -k pour demander le mot de passe via stdin.
        """
        # Demander le mot de passe via le bridge
        if not self.bridge:
            return ExecutionResult(
                success=False,
                return_code=-1,
                stdout="",
                stderr="",
                execution_time=time.time() - start_time,
                error_message="Bridge non disponible pour l'authentification sudo"
            )
        
        # Construire la commande avec sudo
        base_cmd = self._build_command(task_node)
        cmd = ["sudo", "-S", "-k", "--"] + base_cmd
        
        # Demander le mot de passe
        password = self._request_sudo_password(task_node)
        if not password:
            return ExecutionResult(
                success=False,
                return_code=-1,
                stdout="",
                stderr="",
                execution_time=time.time() - start_time,
                error_message="Authentification sudo annulée"
            )
        
        try:
            # Exécuter avec sudo
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=task_node.working_dir,
                env={**os.environ, **task_node.env}
            )
            
            # Injecter le mot de passe
            stdout, stderr = proc.communicate(input=f"{password}\n", timeout=task_node.timeout)
            
            return ExecutionResult(
                success=proc.returncode == 0,
                return_code=proc.returncode,
                stdout=stdout,
                stderr=stderr,
                execution_time=time.time() - start_time
            )
        except subprocess.TimeoutExpired:
            proc.kill()
            return ExecutionResult(
                success=False,
                return_code=-1,
                stdout="",
                stderr="",
                execution_time=time.time() - start_time,
                error_message="Timeout expiré"
            )
    
    def _execute_chroot(self, task_node: TaskNode, start_time: float) -> ExecutionResult:
        """
        Exécution dans la cage chroot.
        
        Monte les API kernel nécessaires, exécute dans chroot, puis démonte.
        """
        # Monter les systèmes de fichiers nécessaires
        self._mount_chroot_apis()
        
        try:
            # Construire la commande chroot
            base_cmd = self._build_command(task_node)
            cmd = ["chroot", self.chroot_base] + base_cmd
            
            # Exécuter dans chroot
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env={**os.environ, **task_node.env},
                timeout=task_node.timeout
            )
            
            return ExecutionResult(
                success=result.returncode == 0,
                return_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                execution_time=time.time() - start_time
            )
        finally:
            # Toujours démonter, même en cas d'erreur
            self._unmount_chroot_apis()
    
    def _mount_chroot_apis(self):
        """Monte les API kernel nécessaires dans la cage."""
        apis = ["/dev", "/proc", "/sys"]
        
        for api in apis:
            target = os.path.join(self.chroot_base, api.lstrip("/"))
            if os.path.exists(api) and os.path.exists(os.path.dirname(target)):
                try:
                    subprocess.run(
                        ["mount", "--bind", api, target],
                        check=True,
                        capture_output=True
                    )
                    self._mount_points.append(target)
                    logger.debug(f"Monté {api} -> {target}")
                except subprocess.CalledProcessError as e:
                    logger.warning(f"Échec du montage de {api}: {e}")
    
    def _unmount_chroot_apis(self):
        """Démonte les API kernel de la cage."""
        for mount_point in reversed(self._mount_points):
            try:
                subprocess.run(
                    ["umount", "-l", mount_point],
                    check=False,
                    capture_output=True
                )
                logger.debug(f"Démonté {mount_point}")
            except Exception as e:
                logger.warning(f"Échec du démontage de {mount_point}: {e}")
        
        self._mount_points.clear()
    
    def _request_sudo_password(self, task_node: TaskNode) -> Optional[str]:
        """Demande un mot de passe sudo via le bridge."""
        # Cette méthode sera implémentée dans le scheduler principal
        # qui a accès au bridge global
        return None
    
    def _build_command(self, task_node: TaskNode) -> List[str]:
        """Construit la liste de commande à partir du TaskNode."""
        if isinstance(task_node.command, list):
            return task_node.command
        else:
            # Split la commande string en arguments
            return shlex.split(task_node.command)
    
    def _validate_security(self, task_node: TaskNode) -> bool:
        """
        Validation de sécurité finale.
        
        Vérifie que les arguments de commande sont cohérents avec
        les politiques définies dans defaults.ini.
        """
        if not self.config:
            return True  # Pas de validation sans config
        
        # Récupérer les politiques
        policies = self.config.get("security.policies", {})
        
        # Vérifier les chemins de disque protégés
        protected_disks = policies.get("protected_disks", [])
        command_str = " ".join(self._build_command(task_node))
        
        for disk in protected_disks:
            if disk in command_str:
                logger.warning(f"Tentative d'accès à un disque protégé: {disk}")
                return False
        
        # Vérifier les commandes dangereuses
        dangerous_commands = policies.get("dangerous_commands", [])
        for cmd in dangerous_commands:
            if command_str.startswith(cmd):
                logger.warning(f"Commande dangereuse détectée: {cmd}")
                return False
        
        return True
