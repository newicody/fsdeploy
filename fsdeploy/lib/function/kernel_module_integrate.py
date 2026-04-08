"""
Intégration des modules du noyau détectés dans le système cible (initramfs).
"""
import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional

from fsdeploy.lib.scheduler.model.task import Task


class KernelModuleIntegrateTask(Task):
    """
    Intègre les modules détectés (squashfs, partitions) dans l'initramfs
    du système cible ou live.
    """

    def execute(self) -> Dict[str, Any]:
        self.log_event("kernel.module.integrate.started", {"params": self.params})
        
        target_root = self.params.get("target_root", "/")
        modules_source = self.params.get("modules_source", [])  # liste de chemins de modules
        rebuild_initramfs = self.params.get("rebuild_initramfs", False)
        
        # Vérification du système cible
        target_path = Path(target_root)
        if not target_path.exists():
            result = {
                "target_root": target_root,
                "modules_integrated": [],
                "errors": [f"Le répertoire cible {target_root} n'existe pas."],
                "rebuild_attempted": False,
                "rebuild_log": "",
            }
            self.log_event("kernel.module.integrate.completed_with_errors", result)
            return result
        
        # Chercher le répertoire d'initramfs
        initramfs_dir = self._locate_initramfs_dir(target_root)
        if not initramfs_dir:
            result = {
                "target_root": target_root,
                "modules_integrated": [],
                "errors": ["Impossible de localiser le répertoire initramfs."],
                "rebuild_attempted": False,
                "rebuild_log": "",
            }
            self.log_event("kernel.module.integrate.completed_with_errors", result)
            return result
        
        modules_dir = initramfs_dir / "modules"
        modules_dir.mkdir(parents=True, exist_ok=True)
        
        integrated = []
        errors = []
        
        for src in modules_source:
            src_path = Path(src)
            if not src_path.exists():
                errors.append(f"source introuvable: {src}")
                continue
            dst = modules_dir / src_path.name
            try:
                # Vérifier si déjà présent avec le même contenu
                if dst.exists():
                    # Comparer les tailles et timestamps
                    if src_path.stat().st_size == dst.stat().st_size and \
                       src_path.stat().st_mtime <= dst.stat().st_mtime:
                        integrated.append(str(dst) + " (déjà présent)")
                        continue
                shutil.copy2(src_path, dst)
                integrated.append(str(dst))
            except Exception as e:
                errors.append(f"Échec copie de {src}: {e}")
        
        # Régénérer l'initramfs si demandé et si des modules ont été intégrés
        rebuild_log = ""
        if rebuild_initramfs and integrated:
            rebuild_log = self._regenerate_initramfs(target_root)
            if "error" in rebuild_log.lower():
                errors.append(f"Erreur lors de la regénération: {rebuild_log}")
        
        result = {
            "target_root": target_root,
            "initramfs_dir": str(initramfs_dir),
            "modules_integrated": integrated,
            "errors": errors,
            "rebuild_attempted": rebuild_initramfs,
            "rebuild_log": rebuild_log,
        }
        if errors:
            self.log_event("kernel.module.integrate.completed_with_errors", result)
        else:
            self.log_event("kernel.module.integrate.completed", result)
        return result
    
    def _locate_initramfs_dir(self, target_root: str) -> Optional[Path]:
        """Retourne le chemin du répertoire initramfs selon la distribution."""
        candidates = [
            Path(target_root) / "usr/lib/initramfs",
            Path(target_root) / "etc/initramfs-tools",
            Path(target_root) / "usr/lib/dracut",
            Path(target_root) / "lib/dracut",
            Path(target_root) / "usr/lib/mkinitcpio",
        ]
        for cand in candidates:
            if cand.exists() and cand.is_dir():
                return cand
        # Si aucun, créer usr/lib/initramfs par défaut
        default = Path(target_root) / "usr/lib/initramfs"
        return default
    
    def _regenerate_initramfs(self, target_root: str) -> str:
        """Exécute la commande appropriée pour regénérer l'initramfs."""
        # Commandes natives avec support de racine cible (sans chroot)
        # Elles peuvent être plus fiables car n'ont pas besoin d'environnement chroot complet
        native_cmds = []
        if target_root == "/":
            native_cmds.append(["update-initramfs", "-u", "-k", "all"])
            native_cmds.append(["dracut", "--force", "--hostonly"])
            native_cmds.append(["mkinitcpio", "-P"])
        else:
            native_cmds.append(["update-initramfs", "-u", "-k", "all", "-b", target_root])
            native_cmds.append(["dracut", "--force", "--hostonly", "--sysroot", target_root])
            native_cmds.append(["mkinitcpio", "-P", "-r", target_root])
            # Variante alternative pour dracut
            native_cmds.append(["dracut", "--force", "--hostonly", "--root", target_root])
        
        for cmd in native_cmds:
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                if result.returncode == 0:
                    return (
                        f"Commande {' '.join(cmd)} réussie:\n"
                        f"{result.stdout}\n{result.stderr}"
                    )
                # Sinon, continuer
            except FileNotFoundError:
                continue
            except subprocess.TimeoutExpired:
                return f"Timeout pour la commande {' '.join(cmd)}"
            except Exception as e:
                # Ne pas retourner tout de suite, essayer la suivante
                continue
        
        # Fallback sur chroot si target_root != "/"
        if target_root != "/":
            base_cmds = [
                ["update-initramfs", "-u", "-k", "all"],
                ["dracut", "--force", "--hostonly"],
                ["mkinitcpio", "-P"],
            ]
            for cmd in base_cmds:
                full_cmd = ["chroot", target_root] + cmd
                try:
                    result = subprocess.run(
                        full_cmd,
                        capture_output=True,
                        text=True,
                        timeout=120,
                    )
                    if result.returncode == 0:
                        return (
                            f"Commande {' '.join(full_cmd)} réussie:\n"
                            f"{result.stdout}\n{result.stderr}"
                        )
                except FileNotFoundError:
                    continue
                except subprocess.TimeoutExpired:
                    return f"Timeout pour la commande {' '.join(full_cmd)}"
                except Exception as e:
                    continue
        
        self.log_event("kernel.module.integrate.regenerate_failed", {"target_root": target_root})
        return "Aucune commande de regénération d'initramfs trouvée."
