"""
Installation des scripts d'intégration pour upstart et sysvinit.
"""
import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any

from fsdeploy.lib.scheduler.model.task import Task


class UpstartSysvInstallTask(Task):
    """
    Installe les scripts d'intégration pour upstart (si détecté) et sysvinit.
    """

    def execute(self) -> Dict[str, Any]:
        self.log_event("init.upstart_sysv.install.started", {"params": self.params})

        target_root = self.params.get("target_root", "/")
        install_upstart = self.params.get("install_upstart", True)
        install_sysvinit = self.params.get("install_sysvinit", True)

        result = {
            "target_root": target_root,
            "upstart_installed": False,
            "sysvinit_installed": False,
            "errors": [],
        }

        # Détection du système d'init live
        # On suppose que la détection a déjà été effectuée par InitConfigDetectTask
        init_system = self.params.get("init_system", "")
        if init_system not in ("upstart", "sysvinit"):
            # Si ce n'est ni upstart ni sysvinit, on considère que l'installation n'est pas nécessaire
            result["skipped"] = True
            result["skip_reason"] = f"Système d'init détecté non pris en charge ou inconnu : {init_system}"
            self.log_event("init.upstart_sysv.install.skipped", result)
            return result

        # Chemins des templates
        contrib_dir = Path(__file__).parent.parent.parent.parent / "contrib"
        upstart_src = contrib_dir / "upstart" / "fsdeploy.conf"
        sysvinit_src = contrib_dir / "sysvinit" / "fsdeploy"

        target_upstart = Path(target_root) / "etc" / "init" / "fsdeploy.conf"
        target_sysvinit = Path(target_root) / "etc" / "init.d" / "fsdeploy"

        if install_upstart and upstart_src.exists() and init_system == "upstart":
            try:
                target_upstart.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(upstart_src, target_upstart)
                # Appliquer les permissions
                target_upstart.chmod(0o644)
                result["upstart_installed"] = True
                self.log_event("init.upstart_sysv.install.upstart_done",
                               {"config": str(target_upstart)})
            except Exception as e:
                result["errors"].append(f"Échec installation upstart : {e}")

        if install_sysvinit and sysvinit_src.exists() and init_system == "sysvinit":
            try:
                target_sysvinit.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(sysvinit_src, target_sysvinit)
                target_sysvinit.chmod(0o755)
                # Mettre à jour les runlevels selon la distribution
                self._update_runlevels(target_sysvinit, target_root)
                result["sysvinit_installed"] = True
                self.log_event("init.upstart_sysv.install.sysvinit_done",
                               {"script": str(target_sysvinit)})
            except Exception as e:
                result["errors"].append(f"Échec installation sysvinit : {e}")

        self.log_event("init.upstart_sysv.install.completed", result)
        return result

    def _update_runlevels(self, script_path: Path, target_root: str) -> None:
        """Active le script sysvinit dans les runlevels par défaut."""
        # On utilise update-rc.d si disponible, sinon chkconfig
        if shutil.which("update-rc.d"):
            subprocess.run(
                ["update-rc.d", script_path.name, "defaults"],
                cwd=target_root if target_root != "/" else None,
                capture_output=True,
            )
        elif shutil.which("chkconfig"):
            subprocess.run(
                ["chkconfig", "--add", script_path.name],
                cwd=target_root if target_root != "/" else None,
                capture_output=True,
            )
        # Sinon, pas d'erreur, l'utilisateur devra configurer manuellement.


class UpstartSysvTestTask(Task):
    """
    Vérifie l'installation et la configuration des scripts upstart et sysvinit.
    """

    def execute(self) -> Dict[str, Any]:
        self.log_event("init.upstart_sysv.test.started", {"params": self.params})

        target_root = self.params.get("target_root", "/")
        init_system = self.params.get("init_system", "")

        result = {
            "target_root": target_root,
            "init_system": init_system,
            "checks_passed": [],
            "checks_failed": [],
            "errors": [],
        }

        if init_system not in ("upstart", "sysvinit"):
            result["errors"].append(f"Système d'init non pris en charge pour les tests: {init_system}")
            self.log_event("init.upstart_sysv.test.skipped", result)
            return result

        # Vérifier la présence des fichiers de configuration
        if init_system == "upstart":
            conf_path = Path(target_root) / "etc" / "init" / "fsdeploy.conf"
            if conf_path.exists():
                result["checks_passed"].append("fichier upstart présent")
                # Vérifier la syntaxe basique
                try:
                    content = conf_path.read_text()
                    if "exec" in content and "fsdeploy" in content:
                        result["checks_passed"].append("fichier upstart semble valide")
                    else:
                        result["checks_failed"].append("fichier upstart semble invalide")
                except Exception as e:
                    result["checks_failed"].append(f"erreur lecture fichier upstart: {e}")
            else:
                result["checks_failed"].append("fichier upstart absent")
        else:  # sysvinit
            script_path = Path(target_root) / "etc" / "init.d" / "fsdeploy"
            if script_path.exists():
                result["checks_passed"].append("script init.d présent")
                # Vérifier les permissions exécutables
                if os.access(script_path, os.X_OK):
                    result["checks_passed"].append("script exécutable")
                else:
                    result["checks_failed"].append("script non exécutable")
                # Vérifier les liens de runlevel
                rc_dirs = [d for d in Path(target_root).glob("etc/rc?.d") if d.is_dir()]
                found_links = []
                for rc_dir in rc_dirs:
                    for link in rc_dir.iterdir():
                        if link.is_symlink() and link.resolve() == script_path.resolve():
                            found_links.append(str(link))
                if found_links:
                    result["checks_passed"].append(f"liens runlevel présents ({len(found_links)})")
                else:
                    result["checks_failed"].append("aucun lien runlevel détecté")
            else:
                result["checks_failed"].append("script init.d absent")

        # Vérifier que le service peut être interrogé (dry-run)
        try:
            if init_system == "upstart":
                # Utiliser initctl status (simulé)
                proc = subprocess.run(
                    ["initctl", "status", "fsdeploy"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                # Peu importe le statut, si la commande fonctionne c'est bon
                result["checks_passed"].append("commande initctl disponible")
            else:
                # Utiliser service --status-all ou directement le script avec status
                script_path = Path(target_root) / "etc" / "init.d" / "fsdeploy"
                if script_path.exists():
                    proc = subprocess.run(
                        [str(script_path), "status"],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    result["checks_passed"].append("script status exécuté")
        except Exception as e:
            result["checks_failed"].append(f"test de statut échoué: {e}")

        self.log_event("init.upstart_sysv.test.completed", result)
        return result
