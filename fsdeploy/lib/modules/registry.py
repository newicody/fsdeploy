"""
Registre des modules tiers pour fsdeploy.
Version simplifiée sans dépendance externe.
"""

import json
import shutil
from pathlib import Path
from typing import List, Dict, Optional

class ModuleRegistry:
    """
    Gère l'interaction avec le registre distant des modules.
    """

    DEFAULT_REGISTRY_URL = "https://api.example.com/fsdeploy/modules.json"
    LOCAL_MODULES_DIR = Path("~/.local/share/fsdeploy/modules").expanduser()

    def __init__(self, config: Optional[object] = None):
        """
        Si config est fourni, on peut en extraire des paramètres.
        Sinon, on utilise des valeurs par défaut.
        """
        # Si config a une méthode get, on l'utilise, sinon on ignore
        self.config = config
        if hasattr(config, 'get'):
            self.registry_url = config.get("module.registry_url", self.DEFAULT_REGISTRY_URL)
            local_dir = config.get("module.local_dir", self.LOCAL_MODULES_DIR)
            self.local_dir = Path(local_dir).expanduser()
        else:
            self.registry_url = self.DEFAULT_REGISTRY_URL
            self.local_dir = self.LOCAL_MODULES_DIR
        self.local_dir.mkdir(parents=True, exist_ok=True)

    def list_remote(self) -> List[Dict]:
        """
        Récupère la liste des modules disponibles depuis le registre distant.
        En cas d'erreur, retourne une liste de démo.
        """
        import requests
        try:
            resp = requests.get(self.registry_url, timeout=5)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            # Fallback sur des données de démonstration
            return [
                {
                    "name": "zfs-snapshots-advanced",
                    "version": "1.2.0",
                    "description": "Gestion avancée des snapshots ZFS avec planification",
                    "author": "fsdeploy-contrib"
                },
                {
                    "name": "kernel-utils",
                    "version": "0.9.5",
                    "description": "Outils supplémentaires pour la compilation et la gestion des noyaux",
                    "author": "fsdeploy-contrib"
                },
                {
                    "name": "health-dashboard",
                    "version": "2.1.0",
                    "description": "Tableau de bord de santé système avec alertes",
                    "author": "fsdeploy-contrib"
                },
                {
                    "name": "legacy-filesystems",
                    "version": "1.0.3",
                    "description": "Support étendu pour les systèmes de fichiers legacy (ext2, ext3, XFS)",
                    "author": "fsdeploy-contrib"
                },
            ]

    def is_installed(self, module_name: str) -> bool:
        """Vérifie si un module est déjà installé localement."""
        module_path = self.local_dir / module_name
        return module_path.exists()

    def install(self, module_name: str, version: Optional[str] = None) -> None:
        """
        Installe (ou met à jour) un module depuis le registre.
        Pour l'instant, simule l'installation en créant un répertoire vide.
        """
        module_path = self.local_dir / module_name
        module_path.mkdir(exist_ok=True)
        # Créer un fichier metadata.json minimal
        meta = {
            "name": module_name,
            "version": version or "1.0.0",
            "installed_by": "registry",
        }
        (module_path / "metadata.json").write_text(json.dumps(meta, indent=2))
        # Note : dans une implémentation réelle, on clonerait un dépôt Git
        # ou on téléchargerait une archive.

    def uninstall(self, module_name: str) -> None:
        """Désinstalle un module."""
        module_path = self.local_dir / module_name
        if module_path.exists():
            shutil.rmtree(module_path)

    def update_all(self) -> Dict[str, bool]:
        """
        Met à jour tous les modules installés.
        Retourne un dictionnaire module -> succès.
        """
        import time
        results = {}
        for path in self.local_dir.iterdir():
            if path.is_dir():
                # Pour l'instant, simplement mettre à jour le fichier metadata
                meta_file = path / "metadata.json"
                if meta_file.exists():
                    try:
                        meta = json.loads(meta_file.read_text())
                        meta["last_updated"] = time.time()
                        meta_file.write_text(json.dumps(meta, indent=2))
                        results[path.name] = True
                    except Exception:
                        results[path.name] = False
        return results
