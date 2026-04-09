"""
Scanner pour les images SquashFS.
"""

import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, List

from fsdeploy.lib.modules.loader import FsDeployModule, ModuleLoader


class SquashfsScannerModule(FsDeployModule):
    """Module d'analyse SquashFS."""

    name = "squashfs_scanner"
    version = "2.0.0"
    description = "Analyse les images SquashFS pour extraire les noyaux, initramfs, etc. Permet également l'extraction sélective."

    def on_load(self) -> None:
        """Enregistre le scanner auprès du loader."""
        self.loader.register_scanner("squashfs", self.scan_squashfs)
        self.loader.register_scanner("squashfs_extract", self.extract_files)
        print(f"[INFO] Scanner SquashFS enregistré.")

    def scan_squashfs(self, image_path: Path) -> Dict[str, Any]:
        """
        Analyse une image SquashFS.
        Retourne un dictionnaire avec les éléments trouvés, incluant les chemins relatifs.
        """
        result = {
            "kernel": [],
            "initramfs": [],
            "modules": [],
            "rootfs": [],
            "other": [],
            "paths": []
        }
        if not image_path.exists():
            return result
        # Utilise unsquashfs -l pour lister les fichiers
        try:
            proc = subprocess.run(
                ["unsquashfs", "-l", str(image_path)],
                capture_output=True,
                text=True,
                timeout=30
            )
            if proc.returncode != 0:
                return result
            lines = proc.stdout.splitlines()
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                # Extraire le chemin qui apparaît après la date
                # Format : permissions user/group size date time path
                parts = line.split()
                if len(parts) < 6:
                    continue
                # Le chemin est la partie après la cinquième colonne (index 5)
                # On joint au cas où le chemin contient des espaces
                path = ' '.join(parts[5:])
                # Enlever le préfixe "squashfs-root/" si présent
                prefix = "squashfs-root/"
                if path.startswith(prefix):
                    rel_path = path[len(prefix):]
                else:
                    rel_path = path
                result["paths"].append(rel_path)
                # Détection par type
                lower_path = rel_path.lower()
                if any(p in lower_path for p in ["vmlinuz", "bzimage", "kernel"]):
                    result["kernel"].append(rel_path)
                elif any(p in lower_path for p in ["initrd", "initramfs"]):
                    result["initramfs"].append(rel_path)
                elif any(p in lower_path for p in [".ko", "modules/"]):
                    result["modules"].append(rel_path)
                elif any(p in lower_path for p in ["root", "fs"]) and "squashfs-root" in path:
                    result["rootfs"].append(rel_path)
                else:
                    result["other"].append(rel_path)
        except Exception as e:
            print(f"[ERROR] Erreur lors de l'analyse de {image_path}: {e}")
        return result

    def extract_files(self, image_path: Path, file_patterns: List[str], output_dir: Optional[Path] = None) -> Dict[str, List[str]]:
        """
        Extrait les fichiers correspondant aux motifs depuis l'image SquashFS vers un répertoire de sortie.
        Retourne un dict des fichiers extraits par catégorie.
        """
        extracted = {pattern: [] for pattern in file_patterns}
        if not image_path.exists():
            return extracted
        # Créer un répertoire temporaire si aucun répertoire de sortie n'est fourni
        temp_dir_ctx = None
        if output_dir is None:
            temp_dir_ctx = tempfile.TemporaryDirectory()
            output_dir = Path(temp_dir_ctx.name)
        else:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Pour chaque motif, on utilise unsquashfs -f -d pour extraire sélectivement
            for pattern in file_patterns:
                # unsquashfs -f -d destination image 'pattern'
                cmd = ["unsquashfs", "-f", "-d", str(output_dir), str(image_path), pattern]
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                if proc.returncode == 0:
                    # Chercher les fichiers extraits correspondant au motif dans output_dir
                    for file_path in output_dir.glob(pattern):
                        if file_path.is_file():
                            extracted[pattern].append(str(file_path.relative_to(output_dir)))
                else:
                    print(f"[WARN] Échec de l'extraction pour {pattern}: {proc.stderr}")
            # Si c'était un temporaire, on ne supprime pas tout de suite (les fichiers sont utilisables jusqu'à la fin du contexte)
            if temp_dir_ctx is not None:
                # On garde le contexte ouvert, l'appelant doit gérer.
                self._temp_dir = temp_dir_ctx  # stocker pour éviter GC immédiat
        except Exception as e:
            print(f"[ERROR] Erreur lors de l'extraction depuis {image_path}: {e}")
        finally:
            # Si on a créé un temporaire, on le laisse vivre (responsabilité de l'appelant de le nettoyer)
            pass
        return extracted
