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
import os
import shlex
import select
import fcntl
from typing import Optional, Dict, Any, List, Callable, Union
from dataclasses import dataclass, field
from enum import Enum

from fsdeploy.lib.log import get_logger
from .injector import resolve_command, sanitize_value, MissingVariableError
from .cage import cage_context

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
    command: str = ""
    mode: str = "standard"


class ExecutionMode(Enum):
    """Modes d'exécution supportés."""
    STANDARD = "standard"      # Exécution normale
    SUDO = "sudo"             # Exécution avec élévation de privilèges
    CHROOT = "chroot"         # Exécution en environnement isolé
    SUDO_CHROOT = "sudo_chroot"  # Sudo + chroot


class TaskRunner:
    """
    Runner pour l'exécution des tâches avec injection, isolation et sudo.
    
    Gère trois tunnels d'exécution :
      - Standard : commande normale
      - Sudo : avec élévation via bridge
      - Chroot : isolation dans une cage
    """
    
    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        bridge=None,
        cage_path: str = "/opt/fsdeploy/bootstrap",
        sudo_password: Optional[str] = None,
        on_output: Optional[Callable[[str, str], None]] = None
    ):
        """
        Initialise le runner.
        
        Args:
            config: Configuration pour l'injection
            bridge: Bridge pour les requêtes sudo et le streaming des logs
            cage_path: Chemin vers la cage chroot
            sudo_password: Mot de passe sudo (optionnel)
            on_output: Callback pour le streaming des logs
        """
        self.config = config or {}
        self.bridge = bridge
        self.cage_path = cage_path
        self.sudo_password = sudo_password
        self.on_output = on_output
        self._active_processes = {}
        self._lock = threading.RLock()
        
    def run_task(
        self,
        command: str,
        context: Optional[Dict[str, Any]] = None,
        mode: Union[ExecutionMode, str] = ExecutionMode.STANDARD,
        chroot_path: Optional[str] = None,
        timeout: Optional[float] = None,
        log_callback: Optional[Callable[[str, str], None]] = None,
        sudo_password: Optional[str] = None,
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        ticket_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Exécute une tâche avec les paramètres donnés.
        
        Args:
            command: Commande brute avec variables
            context: Contexte pour l'injection
            mode: Mode d'exécution
            chroot_path: Chemin pour chroot (si mode CHROOT)
            timeout: Timeout en secondes
            log_callback: Callback pour les logs (type, message)
            sudo_password: Mot de passe sudo (si mode SUDO)
            cwd: Répertoire de travail
            env: Variables d'environnement
            ticket_id: ID du ticket associé pour le streaming des logs
            
        Returns:
            Dictionnaire avec résultats
        """
        if context is None:
            context = {}
        
        # Convertir le mode en enum si nécessaire
        if isinstance(mode, str):
            mode = ExecutionMode(mode.lower())
        
        # 1. Validation et injection
        try:
            injected_cmd = resolve_command(command, self.config)
        except ValueError as e:
            return {
                "success": False,
                "error": str(e),
                "exit_code": -1,
                "command": command,
                "injected_command": None
            }
        
        # 2. Préparation de la commande selon le mode
        if mode == ExecutionMode.CHROOT:
            target_path = chroot_path or self.cage_path
            return self._run_chroot(
                injected_cmd, target_path, timeout, log_callback, cwd, env, ticket_id
            )
        elif mode == ExecutionMode.SUDO:
            return self._run_sudo(
                injected_cmd, sudo_password, timeout, log_callback, cwd, env, ticket_id
            )
        elif mode == ExecutionMode.SUDO_CHROOT:
            target_path = chroot_path or self.cage_path
            return self._run_sudo_chroot(
                injected_cmd, target_path, sudo_password, timeout, log_callback, cwd, env, ticket_id
            )
        else:
            return self._run_standard(
                injected_cmd, timeout, log_callback, cwd, env, ticket_id
            )
    
    def _run_standard(
        self,
        command: str,
        timeout: Optional[float],
        log_callback: Optional[Callable],
        cwd: Optional[str],
        env: Optional[Dict[str, str]],
        ticket_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Exécution standard."""
        return self._execute_command(
            command, timeout, log_callback, cwd, env, ticket_id=ticket_id
        )
    
    def _run_sudo(
        self,
        command: str,
        password: Optional[str],
        timeout: Optional[float],
        log_callback: Optional[Callable],
        cwd: Optional[str],
        env: Optional[Dict[str, str]],
        ticket_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Exécution avec sudo."""
        sudo_cmd = f"sudo -S {command}"
        
        if password:
            # Exécution avec mot de passe fourni
            return self._execute_command(
                sudo_cmd, timeout, log_callback, cwd, env, 
                stdin_input=password + "\n", ticket_id=ticket_id
            )
        elif self.bridge:
            # Demande interactive via bridge
            return self._execute_with_sudo_request(
                command, timeout, log_callback, cwd, env, ticket_id
            )
        else:
            return {
                "success": False,
                "error": "Sudo requis mais aucun bridge disponible",
                "exit_code": -1,
                "command": command
            }
    
    def _run_chroot(
        self,
        command: str,
        chroot_path: str,
        timeout: Optional[float],
        log_callback: Optional[Callable],
        cwd: Optional[str],
        env: Optional[Dict[str, str]],
        ticket_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Exécution en chroot."""
        try:
            with cage_context(chroot_path):
                # Préparer la commande chroot
                chroot_cmd = f"chroot {chroot_path} {command}"
                return self._execute_command(
                    chroot_cmd, timeout, log_callback, cwd, env, ticket_id=ticket_id
                )
        except Exception as e:
            return {
                "success": False,
                "error": f"Échec chroot: {str(e)}",
                "exit_code": -1,
                "command": command
            }
    
    def _run_sudo_chroot(
        self,
        command: str,
        chroot_path: str,
        password: Optional[str],
        timeout: Optional[float],
        log_callback: Optional[Callable],
        cwd: Optional[str],
        env: Optional[Dict[str, str]],
        ticket_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Exécution sudo + chroot."""
        sudo_chroot_cmd = f"sudo -S chroot {chroot_path} {command}"
        
        if password:
            return self._execute_command(
                sudo_chroot_cmd, timeout, log_callback, cwd, env, 
                stdin_input=password + "\n", ticket_id=ticket_id
            )
        else:
            return {
                "success": False,
                "error": "Sudo requis pour chroot mais mot de passe non fourni",
                "exit_code": -1,
                "command": command
            }
    
    def _stream_output(
        self,
        process: subprocess.Popen,
        stdout_callback: Optional[Callable[[str], None]] = None,
        stderr_callback: Optional[Callable[[str], None]] = None,
        ticket_id: Optional[str] = None
    ) -> None:
        """
        Stream la sortie d'un processus en temps réel.
        """
        # Rendre les pipes non-bloquants
        for pipe in [process.stdout, process.stderr]:
            if pipe:
                fd = pipe.fileno()
                fl = fcntl.fcntl(fd, fcntl.F_GETFL)
                fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
        
        buffers = {process.stdout: "", process.stderr: ""}
        
        while process.poll() is None:
            # Surveiller les pipes avec select
            readable, _, _ = select.select(
                [process.stdout, process.stderr],
                [],
                [],
                0.1
            )
            
            for pipe in readable:
                if pipe == process.stdout:
                    callback = stdout_callback
                    buffer_key = process.stdout
                    stream_type = "stdout"
                else:
                    callback = stderr_callback
                    buffer_key = process.stderr
                    stream_type = "stderr"
                
                try:
                    chunk = pipe.read(4096)
                    if chunk:
                        if isinstance(chunk, bytes):
                            chunk = chunk.decode('utf-8', errors='replace')
                        
                        buffers[buffer_key] += chunk
                        
                        while '\n' in buffers[buffer_key]:
                            line, buffers[buffer_key] = buffers[buffer_key].split('\n', 1)
                            
                            # Émettre le log via le bridge si disponible
                            if self.bridge and hasattr(self.bridge, 'emit_log'):
                                level = "error" if stream_type == "stderr" else "info"
                                self.bridge.emit_log(
                                    log=line,
                                    stream=stream_type,
                                    ticket_id=ticket_id,
                                    level=level
                                )
                            
                            if callback:
                                callback(line)
                            
                            if self.on_output:
                                self.on_output(stream_type, line)
                except (IOError, OSError):
                    pass
        
        # Lire les données restantes
        for pipe, buffer in buffers.items():
            if pipe and buffer:
                for line in buffer.split('\n'):
                    if line:
                        stream_type = "stdout" if pipe == process.stdout else "stderr"
                        
                        # Émettre le log via le bridge si disponible
                        if self.bridge and hasattr(self.bridge, 'emit_log'):
                            level = "error" if stream_type == "stderr" else "info"
                            self.bridge.emit_log(
                                log=line,
                                stream=stream_type,
                                ticket_id=ticket_id,
                                level=level
                            )
                        
                        if pipe == process.stdout and stdout_callback:
                            stdout_callback(line)
                        elif pipe == process.stderr and stderr_callback:
                            stderr_callback(line)
                        
                        if self.on_output:
                            self.on_output(stream_type, line)
    
    def _execute_command(
        self,
        command: str,
        timeout: Optional[float],
        log_callback: Optional[Callable],
        cwd: Optional[str],
        env: Optional[Dict[str, str]],
        stdin_input: Optional[str] = None,
        ticket_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Exécute une commande avec subprocess.
        
        Gère les flux stdout/stderr en temps réel.
        """
        process_id = str(time.time())
        
        try:
            # Préparer l'environnement
            process_env = os.environ.copy()
            if env:
                process_env.update(env)
            
            # Démarrer le processus
            proc = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE if stdin_input else None,
                cwd=cwd,
                env=process_env,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Enregistrer le processus
            with self._lock:
                self._active_processes[process_id] = proc
            
            # Gérer l'entrée stdin si nécessaire
            if stdin_input and proc.stdin:
                proc.stdin.write(stdin_input)
                proc.stdin.flush()
                proc.stdin.close()
            
            # Streamer la sortie en temps réel
            stdout_lines = []
            stderr_lines = []
            
            def collect_stdout(line: str) -> None:
                stdout_lines.append(line)
            
            def collect_stderr(line: str) -> None:
                stderr_lines.append(line)
            
            self._stream_output(proc, collect_stdout, collect_stderr, ticket_id)
            
            # Attendre la fin du processus
            returncode = proc.wait(timeout=timeout)
            
            return {
                "success": returncode == 0,
                "exit_code": returncode,
                "stdout": '\n'.join(stdout_lines),
                "stderr": '\n'.join(stderr_lines),
                "command": command,
                "process_id": process_id
            }
            
        except subprocess.TimeoutExpired:
            # Timeout - tuer le processus
            if process_id in self._active_processes:
                self._active_processes[process_id].kill()
            
            return {
                "success": False,
                "error": f"Timeout après {timeout} secondes",
                "exit_code": -1,
                "command": command,
                "process_id": process_id
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "exit_code": -1,
                "command": command,
                "process_id": process_id
            }
            
        finally:
            # Nettoyer
            with self._lock:
                self._active_processes.pop(process_id, None)
    
    def _execute_with_sudo_request(
        self,
        command: str,
        timeout: Optional[float],
        log_callback: Optional[Callable],
        cwd: Optional[str],
        env: Optional[Dict[str, str]],
        ticket_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Exécute une commande avec demande sudo interactive via bridge.
        """
        # Émettre un événement de demande sudo
        if self.bridge and hasattr(self.bridge, 'emit'):
            sudo_ticket_id = self.bridge.emit(
                "auth.sudo_request",
                command=command,
                timeout=timeout,
                original_ticket=ticket_id
            )
        else:
            sudo_ticket_id = None
        
        # Pour l'instant, retourner un résultat d'attente
        return {
            "success": False,
            "error": "Sudo requis - en attente d'authentification",
            "exit_code": -2,
            "command": command,
            "ticket_id": sudo_ticket_id,
            "pending_auth": True
        }
    
    def kill_process(self, process_id: str) -> bool:
        """
        Tue un processus en cours d'exécution.
        
        Args:
            process_id: ID du processus
            
        Returns:
            True si tué, False sinon
        """
        with self._lock:
            proc = self._active_processes.get(process_id)
            if proc:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                return True
        return False
    
    def get_active_processes(self) -> List[Dict[str, Any]]:
        """
        Retourne la liste des processus actifs.
        
        Returns:
            Liste des informations sur les processus
        """
        with self._lock:
            return [
                {
                    "process_id": pid,
                    "command": "N/A",
                    "alive": proc.poll() is None
                }
                for pid, proc in self._active_processes.items()
            ]


class MultiModeRunner:
    """
    Exécuteur multi-mode pour les tâches du scheduler.
    
    Gère trois modes d'exécution :
    1. Standard : exécution normale
    2. Sudo : exécution avec élévation de privilèges
    3. Chroot : exécution dans la cage bootstrap
    
    Compatible avec l'ancienne interface.
    """
    
    def __init__(self, bridge=None, config=None):
        self.bridge = bridge
        self.config = config or {}
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
                error_message="Tâche bloquée par les politiques de sécurité",
                command=task_node.command,
                mode="standard"
            )
        
        # Injection de variables
        try:
            command_to_execute = resolve_command(task_node.command, self.config)
        except ValueError as e:
            return ExecutionResult(
                success=False,
                return_code=-1,
                stdout="",
                stderr=str(e),
                execution_time=0,
                error_message=str(e),
                command=task_node.command,
                mode="standard"
            )
        
        try:
            if task_node.chroot:
                return self._execute_chroot(task_node, command_to_execute, start_time)
            elif task_node.root:
                return self._execute_sudo(task_node, command_to_execute, start_time)
            else:
                return self._execute_standard(task_node, command_to_execute, start_time)
        except Exception as e:
            return ExecutionResult(
                success=False,
                return_code=-1,
                stdout="",
                stderr=str(e),
                execution_time=time.time() - start_time,
                error_message=f"Erreur d'exécution: {e}",
                command=task_node.command,
                mode="chroot" if task_node.chroot else "sudo" if task_node.root else "standard"
            )
    
    def _execute_standard(self, task_node: TaskNode, command: str, start_time: float) -> ExecutionResult:
        """Exécution standard sans privilèges."""
        cmd = self._build_command(task_node, command)
        
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
                execution_time=time.time() - start_time,
                command=command,
                mode="standard"
            )
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                success=False,
                return_code=-1,
                stdout="",
                stderr="",
                execution_time=time.time() - start_time,
                error_message="Timeout expiré",
                command=command,
                mode="standard"
            )
    
    def _execute_sudo(self, task_node: TaskNode, command: str, start_time: float) -> ExecutionResult:
        """
        Exécution avec privilèges root via tunnel sudo.
        """
        if not self.bridge:
            return ExecutionResult(
                success=False,
                return_code=-1,
                stdout="",
                stderr="",
                execution_time=time.time() - start_time,
                error_message="Bridge non disponible pour l'authentification sudo",
                command=command,
                mode="sudo"
            )
        
        base_cmd = self._build_command(task_node, command)
        cmd = ["sudo", "-S", "-k", "--"] + base_cmd
        
        password = self._request_sudo_password(task_node)
        if not password:
            return ExecutionResult(
                success=False,
                return_code=-1,
                stdout="",
                stderr="",
                execution_time=time.time() - start_time,
                error_message="Authentification sudo annulée",
                command=command,
                mode="sudo"
            )
        
        try:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=task_node.working_dir,
                env={**os.environ, **task_node.env}
            )
            
            stdout, stderr = proc.communicate(input=f"{password}\n", timeout=task_node.timeout)
            
            return ExecutionResult(
                success=proc.returncode == 0,
                return_code=proc.returncode,
                stdout=stdout,
                stderr=stderr,
                execution_time=time.time() - start_time,
                command=command,
                mode="sudo"
            )
        except subprocess.TimeoutExpired:
            proc.kill()
            return ExecutionResult(
                success=False,
                return_code=-1,
                stdout="",
                stderr="",
                execution_time=time.time() - start_time,
                error_message="Timeout expiré",
                command=command,
                mode="sudo"
            )
    
    def _execute_chroot(self, task_node: TaskNode, command: str, start_time: float) -> ExecutionResult:
        """
        Exécution dans la cage chroot.
        """
        try:
            with cage_context(self.chroot_base):
                base_cmd = self._build_command(task_node, command)
                cmd = ["chroot", self.chroot_base] + base_cmd
                
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
                    execution_time=time.time() - start_time,
                    command=command,
                    mode="chroot"
                )
        except Exception as e:
            return ExecutionResult(
                success=False,
                return_code=-1,
                stdout="",
                stderr=str(e),
                execution_time=time.time() - start_time,
                error_message=f"Erreur chroot: {e}",
                command=command,
                mode="chroot"
            )
    
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
        return None
    
    def _build_command(self, task_node: TaskNode, command: str = None) -> List[str]:
        """Construit la liste de commande à partir du TaskNode."""
        if command is None:
            command = task_node.command
            
        if isinstance(command, list):
            return command
        else:
            return shlex.split(command)
    
    def _validate_security(self, task_node: TaskNode) -> bool:
        """
        Validation de sécurité finale.
        """
        if not self.config:
            return True
        
        policies = self.config.get("security.policies", {})
        
        protected_disks = policies.get("protected_disks", [])
        command_str = " ".join(self._build_command(task_node))
        
        for disk in protected_disks:
            if disk in command_str:
                logger.warning(f"Tentative d'accès à un disque protégé: {disk}")
                return False
        
        dangerous_commands = policies.get("dangerous_commands", [])
        for cmd in dangerous_commands:
            if command_str.startswith(cmd):
                logger.warning(f"Commande dangereuse détectée: {cmd}")
                return False
        
        return True


# Singleton global pour le TaskRunner
_runner_instance = None

def get_runner(
    config: Optional[Dict[str, Any]] = None,
    bridge=None,
    cage_path: str = "/opt/fsdeploy/bootstrap",
    sudo_password: Optional[str] = None
) -> TaskRunner:
    """
    Retourne l'instance singleton du runner.
    
    Args:
        config: Configuration pour l'injecteur
        bridge: Bridge pour le streaming des logs et sudo
        cage_path: Chemin vers la cage
        sudo_password: Mot de passe sudo
        
    Returns:
        Instance TaskRunner
    """
    global _runner_instance
    if _runner_instance is None:
        _runner_instance = TaskRunner(
            config=config,
            bridge=bridge,
            cage_path=cage_path,
            sudo_password=sudo_password
        )
    return _runner_instance
