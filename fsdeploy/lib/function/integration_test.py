"""
Tâche de test d'intégration pour différentes distributions.
"""
import platform
import subprocess
import time
import os
from pathlib import Path

from fsdeploy.lib.scheduler.model.task import Task

class IntegrationTestTask(Task):
    """Exécute les tests d'intégration pour la distribution courante."""

    def execute(self):
        self.log_event("integration.test.started", {"params": self.params})
        distro = self._detect_distro()
        test_script = self.params.get("script", f"test_{distro}")
        timeout = self.params.get("timeout", 30)
        result = {
            "distribution": distro,
            "script": test_script,
            "passed": False,
            "output": "",
            "error": ""
        }
        try:
            # Chercher le script dans plusieurs emplacements possibles
            script_path = self._find_script(test_script)
            if script_path is None:
                raise FileNotFoundError(
                    f"Script de test {test_script}.sh introuvable. "
                    f"Vérifiez l'installation de fsdeploy."
                )
            self.log_event("integration.test.running",
                           {"distro": distro, "script": str(script_path)})
            # Exécuter le script
            cmd = ["sh", str(script_path)]
            proc = subprocess.run(
                cmd,
                capture_output=True,
                timeout=timeout,
                text=True
            )
            result["output"] = proc.stdout[:1000]  # limite
            result["error"] = proc.stderr[:1000]
            result["passed"] = proc.returncode == 0
            if proc.returncode == 0:
                self.log_event("integration.test.completed", result)
            else:
                self.log_event("integration.test.failed", result)
        except subprocess.TimeoutExpired:
            result["error"] = f"Timeout après {timeout} secondes"
            self.log_event("integration.test.timeout", result)
        except Exception as e:
            result["error"] = str(e)
            self.log_event("integration.test.failed", result)
        return result

    def _detect_distro(self):
        """Détecte la distribution Linux."""
        import os
        if os.path.exists("/etc/os-release"):
            with open("/etc/os-release") as f:
                for line in f:
                    if line.startswith("ID="):
                        return line.split("=")[1].strip().strip('"')
        return platform.system().lower()

    def _find_script(self, script_name: str) -> Path | None:
        """Cherche le script d'intégration dans différents répertoires."""
        # 1. Chemin relatif au module (développement)
        base = Path(__file__).parent.parent.parent.parent.parent
        candidates = [
            base / "contrib" / "integration" / f"{script_name}.sh",
            base / "contrib" / "integration" / f"{script_name}",
            Path("/usr/share/fsdeploy/contrib/integration") / f"{script_name}.sh",
            Path("/usr/local/share/fsdeploy/contrib/integration") / f"{script_name}.sh",
        ]
        for cand in candidates:
            if cand.is_file():
                return cand
        return None
