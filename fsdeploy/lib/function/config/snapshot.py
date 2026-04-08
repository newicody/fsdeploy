from ..task import Task
import shutil
from pathlib import Path
import time


class ConfigSnapshotTask(Task):
    """Sauvegarder la configuration actuelle dans un snapshot."""

    def before_run(self) -> None:
        self.log(f"[ConfigSnapshotTask] Début snapshot pour {self.params.get('snapshot_name', 'auto')}")

    def run(self):
        # paramètre optionnel : snapshot_name (chaîne) ou vide pour générer automatiquement
        snapshot_name = self.params.get("snapshot_name")
        config_path = Path(self.params.get("config_path", "/etc/fsdeploy/config.fsd"))
        backup_dir = Path("/var/lib/fsdeploy/config_snapshots")

        if not config_path.exists():
            self.error = "Le fichier de configuration n'existe pas"
            return False

        backup_dir.mkdir(parents=True, exist_ok=True)

        if not snapshot_name or snapshot_name == "":
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            snapshot_name = f"snap_{timestamp}"

        target = backup_dir / f"config_{snapshot_name}.fsd"

        try:
            shutil.copy2(config_path, target)
        except Exception as e:
            self.error = f"Échec de la copie : {e}"
            return False

        self.result = {
            "snapshot_name": snapshot_name,
            "backup_path": str(target),
            "config_source": str(config_path),
        }
        return True

    def after_run(self, result) -> None:
        if self.error:
            self.log(f"[ConfigSnapshotTask] Échec : {self.error}")
        else:
            self.log(f"[ConfigSnapshotTask] Succès : {self.result}")
