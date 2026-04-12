"""
Tâche de diagnostic pour le mode recovery.
"""

from fsdeploy.lib.scheduler.model.task import Task, CommandResult
from typing import Dict, Any, List, Optional
import subprocess
import sys

class RecoveryDiagnoseTask(Task):
    """Orchestre les vérifications health + coherence et produit un rapport avec actions correctrices."""

    def __init__(self, auto_fix: bool = False, pool: Optional[str] = None):
        super().__init__()
        self.auto_fix = auto_fix
        self.pool = pool
        self.health_report: Dict[str, Any] = {}
        self.coherence_report: Dict[str, Any] = {}

    def run(self) -> CommandResult:
        self.log_event("recovery_diagnose_start", auto_fix=self.auto_fix, pool=self.pool)
        try:
            # 1. HealthCheckTask
            health_ok, health_details = self._run_health_check()
            self.health_report = {
                "ok": health_ok,
                "details": health_details,
                "fixes": []  # liste de corrections suggérées
            }
            # 2. CoherenceCheckTask (quick_mode=True)
            coherence_ok, coherence_details = self._run_coherence_check()
            self.coherence_report = {
                "ok": coherence_ok,
                "details": coherence_details,
                "fixes": []
            }

            # 3. Combiner
            report = {
                "health": self.health_report,
                "coherence": self.coherence_report,
                "actions": self._suggest_actions()
            }

            self.log_event("recovery_diagnose_complete", report=report)
            return CommandResult(
                success=True,
                output=report,
                error=None
            )
        except Exception as e:
            self.log_event("recovery_diagnose_error", error=str(e))
            return CommandResult(
                success=False,
                output=None,
                error=str(e)
            )

    def _run_health_check(self):
        # TODO: intégrer HealthCheckTask existante
        # Pour l'instant, exécuter quelques commandes basiques
        checks = []
        ok = True
        # Vérifier sudo
        try:
            subprocess.run(["sudo", "-n", "true"], capture_output=True, check=False)
            checks.append(("sudo", True, "sudo sans mot de passe possible"))
        except Exception:
            checks.append(("sudo", False, "sudo nécessite un mot de passe"))
            ok = False
        # Vérifier zfs
        try:
            subprocess.run(["which", "zfs"], capture_output=True, check=True)
            checks.append(("zfs", True, "zfs présent"))
        except Exception:
            checks.append(("zfs", False, "zfs non trouvé"))
            ok = False
        # Vérifier espace disque (exemple)
        try:
            df = subprocess.run(["df", "-h", "/"], capture_output=True, text=True, check=True)
            checks.append(("disk_space", True, df.stdout[:80]))
        except Exception:
            checks.append(("disk_space", False, "impossible de vérifier l'espace disque"))
            ok = False
        return ok, checks

    def _run_coherence_check(self):
        # TODO: intégrer CoherenceCheckTask (quick_mode=True)
        checks = []
        ok = True
        # Exemple simple : vérifier montages zfs
        try:
            result = subprocess.run(["zfs", "list", "-H", "-o", "name,mountpoint,mounted"], capture_output=True, text=True)
            lines = result.stdout.strip().split('\n')
            for line in lines:
                if line:
                    parts = line.split('\t')
                    if len(parts) >= 3:
                        name, mountpoint, mounted = parts[0], parts[1], parts[2]
                        if mountpoint != "-" and mounted == "no":
                            checks.append((name, False, f"dataset {name} non monté au point {mountpoint}"))
                            ok = False
        except Exception as e:
            checks.append(("zfs_list", False, f"erreur zfs list: {e}"))
            ok = False
        # Vérifier pools importés
        try:
            result = subprocess.run(["zpool", "list", "-H"], capture_output=True, text=True)
            if result.returncode != 0:
                checks.append(("zpool", False, "échec de zpool list"))
                ok = False
        except Exception as e:
            checks.append(("zpool", False, f"exception zpool: {e}"))
            ok = False
        return ok, checks

    def _suggest_actions(self) -> List[Dict[str, Any]]:
        actions = []
        if not self.health_report.get("ok", False):
            actions.append({
                "type": "health",
                "description": "Corriger les problèmes de santé système",
                "command": "fsdeploy --recovery --fix"
            })
        if not self.coherence_report.get("ok", False):
            actions.append({
                "type": "coherence",
                "description": "Résoudre les incohérences pools/datasets",
                "command": "fsdeploy --recovery --fix --pool ?"
            })
        return actions
