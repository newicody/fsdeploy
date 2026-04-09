"""
Intégration avec ZFSBootMenu : détection et configuration.
"""
import subprocess
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional

from fsdeploy.lib.scheduler.model.task import Task


class ZFSBootMenuIntegrateTask(Task):
    """
    Détecte la présence de ZFSBootMenu et configure le boot via initrc.
    """

    def execute(self) -> Dict[str, Any]:
        self.log_event("zfsbootmenu.integrate.started", {"params": self.params})

        target_root = self.params.get("target_root", "/")
        check_only = self.params.get("check_only", False)
        dry_run = self.params.get("dry_run", False)

        result = {
            "target_root": target_root,
            "zfsbootmenu_detected": False,
            "boot_entries": [],
            "initrc_present": False,
            "initrc_path": "",
            "adjustments_made": [],
            "errors": [],
            "dry_run": dry_run,
        }

        # 1. Détection de ZFSBootMenu
        zbm_paths = [
            Path(target_root) / "boot" / "efi" / "EFI" / "zfsbootmenu",
            Path(target_root) / "boot" / "zfsbootmenu",
            Path(target_root) / "boot" / "EFI" / "zfsbootmenu",
        ]
        detected_path = None
        for p in zbm_paths:
            if p.exists():
                detected_path = p
                break

        if detected_path is None:
            result["errors"].append("ZFSBootMenu non détecté dans les emplacements habituels.")
            self.log_event("zfsbootmenu.integrate.not_found", result)
            return result

        result["zfsbootmenu_detected"] = True
        result["boot_entries"] = [str(p) for p in detected_path.rglob("*.conf") if p.is_file()]

        # 2. Recherche du fichier initrc (ou configuration d'initramfs)
        initrc_candidates = [
            detected_path / "initrc",
            detected_path / "zfsbootmenu-initrc",
            Path(target_root) / "etc" / "zfsbootmenu" / "initrc",
        ]
        initrc_path = None
        for cand in initrc_candidates:
            if cand.exists():
                initrc_path = cand
                break

        if initrc_path:
            result["initrc_present"] = True
            result["initrc_path"] = str(initrc_path)
        else:
            result["errors"].append("Fichier initrc non trouvé.")

        # 3. Si ce n'est pas un simple check, on peut proposer des ajustements
        if not check_only and not dry_run and initrc_path:
            # Lire le contenu actuel
            try:
                content = initrc_path.read_text()
                # Vérifier si fsdeploy est déjà mentionné
                if "fsdeploy" not in content:
                    # Ajouter une ligne d'exemple (à adapter)
                    new_content = content + "\n# Intégration fsdeploy\nexport FS_DEPLOY_ENABLE=1\n"
                    initrc_path.write_text(new_content)
                    result["adjustments_made"].append("Ajout de FS_DEPLOY_ENABLE dans initrc")
            except Exception as e:
                result["errors"].append(f"Impossible de modifier initrc : {e}")

        # 4. Vérifier que le pool ZFS boot existe
        try:
            out = subprocess.run(
                ["zpool", "list", "-H", "-o", "name,bootfs"],
                capture_output=True,
                text=True,
            )
            if out.returncode == 0:
                lines = out.stdout.strip().splitlines()
                for line in lines:
                    if line:
                        pool, bootfs = line.split("\t")
                        if bootfs != "-":
                            result["boot_pool"] = pool
                            result["boot_dataset"] = bootfs
            else:
                result["errors"].append("La commande zpool a échoué.")
        except FileNotFoundError:
            result["errors"].append("zpool non disponible.")

        if result["errors"]:
            self.log_event("zfsbootmenu.integrate.completed_with_errors", result)
        else:
            self.log_event("zfsbootmenu.integrate.completed", result)
        return result
