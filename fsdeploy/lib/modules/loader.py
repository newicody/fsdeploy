"""
Chargeur de modules pour fsdeploy.
"""

import importlib
import inspect
import pkgutil
import sys
from pathlib import Path
from typing import Type, Any, Optional, Dict, List, Callable

from fsdeploy.lib.config import FsDeployConfig


class FsDeployModule:
    """
    Classe de base pour un module.
    """

    name: str = "unnamed"
    version: str = "0.0.0"
    description: str = ""

    def __init__(self, config: FsDeployConfig, loader: 'ModuleLoader'):
        self.config = config
        self.loader = loader

    def on_load(self) -> None:
        """
        Appelé après le chargement du module.
        """
        pass

    def on_unload(self) -> None:
        """
        Appelé avant le déchargement.
        """
        pass


class ModuleLoader:
    """
    Gère le chargement dynamique des modules depuis les répertoires configurés.
    """

    def __init__(self, config: FsDeployConfig):
        self.config = config
        self.modules: Dict[str, FsDeployModule] = {}
        self.scanners: Dict[str, Callable] = {}

    def discover(self, search_paths: Optional[List[str]] = None) -> List[str]:
        """
        Découvre les modules disponibles sans les charger.
        Retourne la liste des noms de modules.
        """
        if search_paths is None:
            search_paths = self.config.get("modules.paths", [])
        found = []
        for path_str in search_paths:
            path = Path(path_str)
            if not path.exists():
                continue
            for entry in path.iterdir():
                if entry.is_file() and entry.name.endswith(".py"):
                    found.append(entry.stem)
                elif entry.is_dir() and (entry / "__init__.py").exists():
                    found.append(entry.name)
        return found

    def load_module(self, name: str) -> bool:
        """
        Charge un module par son nom.
        Le nom peut être un chemin relatif ou un nom de package.
        """
        search_paths = self.config.get("modules.paths", [])
        # Chercher le fichier ou répertoire du module
        for path_str in search_paths:
            base = Path(path_str)
            if not base.exists():
                continue
            # Essayer en tant que fichier .py
            py_file = base / f"{name}.py"
            if py_file.exists() and py_file.is_file():
                return self._load_from_file(py_file, name)
            # Essayer en tant que package
            pkg_dir = base / name
            if pkg_dir.exists() and pkg_dir.is_dir() and (pkg_dir / "__init__.py").exists():
                return self._load_from_package(pkg_dir, name)
        # Si non trouvé, essayer d'importer depuis les chemins Python standards
        try:
            spec = importlib.util.find_spec(name)
            if spec is not None and spec.origin is not None:
                return self._load_from_spec(spec, name)
        except Exception:
            pass
        return False

    def _load_from_file(self, file_path: Path, name: str) -> bool:
        """Charge un module depuis un fichier Python."""
        try:
            spec = importlib.util.spec_from_file_location(name, file_path)
            if spec is None:
                return False
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
            return self._register_module(module, name)
        except Exception as e:
            print(f"[ERROR] Erreur lors du chargement du module {name} depuis {file_path}: {e}")
            return False

    def _load_from_package(self, pkg_dir: Path, name: str) -> bool:
        """Charge un module depuis un package."""
        try:
            spec = importlib.util.spec_from_file_location(name, pkg_dir / "__init__.py")
            if spec is None:
                return False
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
            return self._register_module(module, name)
        except Exception as e:
            print(f"[ERROR] Erreur lors du chargement du package {name} depuis {pkg_dir}: {e}")
            return False

    def _load_from_spec(self, spec, name: str) -> bool:
        """Charge un module depuis une spec déjà trouvée."""
        try:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return self._register_module(module, name)
        except Exception as e:
            print(f"[ERROR] Erreur lors du chargement du module {name} depuis spec: {e}")
            return False

    def _register_module(self, module, name: str) -> bool:
        """Recherche une classe Module dans le module chargé et l'instancie."""
        # Chercher une sous-classe de FsDeployModule dans le module
        for obj_name in dir(module):
            obj = getattr(module, obj_name)
            if (inspect.isclass(obj) and issubclass(obj, FsDeployModule) and
                obj is not FsDeployModule):
                # Instancier
                try:
                    instance = obj(self.config, self)
                    instance.on_load()
                    self.modules[name] = instance
                    print(f"[INFO] Module chargé : {name} ({instance.name} v{instance.version})")
                    return True
                except Exception as e:
                    print(f"[ERROR] Impossible d'instancier le module {name}: {e}")
                    return False
        print(f"[WARN] Aucune classe Module trouvée dans {name}")
        return False

    def register_scanner(self, name: str, scanner_func: Callable) -> None:
        """Enregistre une fonction d'analyse pour un type de fichier."""
        self.scanners[name] = scanner_func

    def load_all(self) -> None:
        """
        Charge tous les modules découverts dans les chemins configurés.
        """
        discovered = self.discover()
        for mod_name in discovered:
            try:
                self.load_module(mod_name)
            except Exception as e:
                print(f"[WARN] Échec du chargement du module {mod_name}: {e}")
