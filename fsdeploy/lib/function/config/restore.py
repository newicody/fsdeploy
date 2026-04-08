from ..task import Task
import shutil
from pathlib import Path
import os
import json

class ConfigRestoreTask(Task):
    """Restaurer une configuration à partir d'un snapshot."""

    def before_run(self) -> None:
        self.log(f"[ConfigRestoreTask] Début restauration pour snapshot '{self.params.get('snapshot_name', 'latest')}'")

    def run(self):
        # paramètre optionnel : snapshot_name (chaîne) ou vide pour le plus récent
        snapshot_name = self.params.get("snapshot_name")
        # Emplacements par défaut (à adapter selon la configuration réelle)
        config_path = Path("/etc/fsdeploy/config.fsd")
        backup_dir = Path("/var/lib/fsdeploy/config_snapshots")

        if not backup_dir.exists():
            self.error = "Le répertoire des snapshots n'existe pas"
            return False

        target = None
        if snapshot_name is None or snapshot_name == "":
            # Trouver le snapshot le plus récent
            snaps = list(backup_dir.glob("config_*.fsd"))
            if not snaps:
                self.error = "Aucun snapshot trouvé"
                return False
            target = max(snaps, key=lambda p: p.stat().st_mtime)
        else:
            target = backup_dir / f"config_{snapshot_name}.fsd"
            if not target.exists():
                self.error = f"Snapshot '{snapshot_name}' introuvable"
                return False

        # Copier le snapshot vers la configuration active
        try:
            shutil.copy2(target, config_path)
        except Exception as e:
            self.error = f"Échec de la copie : {e}"
            return False

        self.result = {
            "restored_from": target.name,
            "config_path": str(config_path),
        }
        return True

    def after_run(self, result) -> None:
        if self.error:
            self.log(f"[ConfigRestoreTask] Échec : {self.error}")
        else:
            self.log(f"[ConfigRestoreTask] Succès : {self.result}")


class ConfigSnapshotListTask(Task):
    """Lister les snapshots de configuration disponibles."""

    def before_run(self) -> None:
        self.log("[ConfigSnapshotListTask] Listing des snapshots")

    def run(self):
        backup_dir = Path("/var/lib/fsdeploy/config_snapshots")
        if not backup_dir.exists():
            self.result = {"snapshots": []}
            return True

        snaps = []
        for p in backup_dir.glob("config_*.fsd"):
            stat = p.stat()
            snaps.append({
                "name": p.stem.replace("config_", ""),
                "filename": p.name,
                "size": stat.st_size,
                "mtime": stat.st_mtime,
            })
        # Trier par mtime décroissant
        snaps.sort(key=lambda x: x["mtime"], reverse=True)
        self.result = {"snapshots": snaps}
        return True

    def after_run(self, result) -> None:
        if self.error:
            self.log(f"[ConfigSnapshotListTask] Échec : {self.error}")
        else:
            self.log(f"[ConfigSnapshotListTask] Succès : {len(self.result.get('snapshots', []))} snapshots listés")
