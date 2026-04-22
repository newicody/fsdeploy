"""
Mapper entre les identifiants d'action et les sections de configuration.
Charge les configurations ConfigObj et établit le mapping Action_ID <-> Config_Section.
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from fsdeploy.lib.config import FsDeployConfig


class ConfigMapper:
    """Mapper qui charge les configurations ConfigObj."""
    
    def __init__(self, config_dirs: List[str] = None):
        """
        Initialise le mapper avec les répertoires de configuration.
        
        Args:
            config_dirs: Liste de chemins vers les répertoires de configuration
        """
        self.configs: Dict[str, FsDeployConfig] = {}
        self.section_map: Dict[str, Dict[str, Any]] = {}
        self.config_dirs = config_dirs or []
        
        # Charger les configurations
        self.reload()
    
    def reload(self):
        """Charge ou recharge toutes les configurations."""
        self.configs.clear()
        self.section_map.clear()
        
        for config_dir in self.config_dirs:
            self._load_configs_from_dir(config_dir)
    
    def _load_configs_from_dir(self, config_dir: str):
        """Charge tous les fichiers de configuration d'un répertoire."""
        config_path = Path(config_dir)
        if not config_path.exists():
            return
        
        # Charger les fichiers .conf, .ini, .cfg
        for config_file in config_path.glob("*.conf"):
            try:
                config = FsDeployConfig(str(config_file))
                config_name = config_file.stem
                self.configs[config_name] = config
                self._build_section_map(config_name, config)
            except Exception as e:
                print(f"Erreur chargement {config_file}: {e}")
    
    def _build_section_map(self, config_name: str, config: FsDeployConfig):
        """Construit le mapping des sections."""
        # Parcourir toutes les sections du fichier de configuration
        # Note: Nous devons adapter cela à la structure de FsDeployConfig
        try:
            if hasattr(config, 'sections'):
                for section in config.sections():
                    section_id = f"{config_name}.{section}"
                    section_data = dict(config[section]) if hasattr(config, '__getitem__') else {}
                    self.section_map[section_id] = {
                        "config_file": config_name,
                        "section_path": section,
                        "data": section_data,
                        "full_id": section_id
                    }
            elif isinstance(config, dict):
                for section_key, section_data in config.items():
                    if isinstance(section_data, dict):
                        section_id = f"{config_name}.{section_key}"
                        self.section_map[section_id] = {
                            "config_file": config_name,
                            "section_path": section_key,
                            "data": section_data,
                            "full_id": section_id
                        }
        except Exception as e:
            print(f"Erreur construction section map pour {config_name}: {e}")
    
    def get_section(self, section_id: str) -> Optional[Dict[str, Any]]:
        """
        Récupère une section de configuration par son ID.
        
        Args:
            section_id: ID de la section (ex: "mounts.root", "kernel.compile")
            
        Returns:
            Dictionnaire contenant la configuration de la section
        """
        return self.section_map.get(section_id)
    
    def get_all_sections(self) -> List[Dict[str, Any]]:
        """Retourne toutes les sections de configuration disponibles."""
        return list(self.section_map.values())
