"""
Tâche générique pour l'exécution de commandes avec support des 3 modes.
"""

from typing import List, Optional
import subprocess


class CommandTask:
    """Tâche pour exécuter une commande shell."""
    
    def __init__(self, command: List[str], 
                 sudo: bool = False,
                 chroot: bool = False,
                 timeout: int = 300,
                 task_id: str = None,
                 **kwargs):
        self.command = command
        self.sudo = sudo
        self.chroot = chroot
        self.timeout = timeout
        self.id = task_id or f"cmd-{hash(tuple(command))}"
        
        # Déterminer le mode d'exécution
        if chroot:
            self.executor = "sudo_chroot"
        elif sudo:
            self.executor = "sudo_host"
        else:
            self.executor = "default"
        
        # Contexte et autres attributs
        self.context = kwargs.get('context', {})
        self.params = kwargs
        
        # Pour compatibilité avec l'Executor
        self._cgroup = None
    
    def get_command(self) -> List[str]:
        """Retourne la commande à exécuter."""
        return self.command
    
    def run(self):
        """Exécution par défaut (sans sudo)."""
        result = subprocess.run(
            self.command,
            capture_output=True,
            text=True,
            timeout=self.timeout,
            check=False
        )
        
        if result.returncode != 0:
            raise subprocess.CalledProcessError(
                result.returncode,
                self.command,
                result.stdout,
                result.stderr
            )
        
        return result.stdout.strip()
    
    def before_run(self):
        """Préparation avant exécution."""
        pass
    
    def after_run(self):
        """Nettoyage après exécution."""
        pass
    
    def set_runtime(self, runtime):
        """Définit le runtime pour la tâche."""
        self.runtime = runtime
    
    def __repr__(self):
        return f"CommandTask(id={self.id}, command={self.command}, executor={self.executor})"
