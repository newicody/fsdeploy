#!/usr/bin/env python3
"""
Point d'entrée principal de fsdeploy.
Permet de lancer l'application en mode terminal.
"""

import sys
import argparse
import json
from pathlib import Path

from fsdeploy.lib.ui.app import FsDeployApp

from fsdeploy.lib.scheduler.runtime import Runtime
from fsdeploy.lib.scheduler.core.scheduler import Scheduler
from fsdeploy.lib.scheduler.core.resolver import Resolver
from fsdeploy.lib.scheduler.core.executor import Executor

    

def main() -> None:
    from fsdeploy.lib.util.logging import setup_logging
    setup_logging()
    


    parser = argparse.ArgumentParser(
        description="fsdeploy - Déploiement et gestion de systèmes de fichiers ZFS"
    )
    parser.add_argument(
        "--log-persist",
        metavar="FICHIER",
        help="Active la persistance des logs dans le fichier indiqué",
    )
    parser.add_argument(
        "--scan-squashfs",
        metavar="FICHIER",
        help="Analyse une image SquashFS et affiche les éléments détectés",
    )
    parser.add_argument(
        "--scan-dir",
        metavar="RÉPERTOIRE",
        help="Analyse tous les fichiers .squashfs du répertoire",
    )
    parser.add_argument(
        "--check-overlay",
        action="store_true",
        help="Vérifie l'intégrité des montages overlayfs existants",
    )
    parser.add_argument(
        "--check-legacy-mounts",
        action="store_true",
        help="Vérifie les montages legacy et les permissions",
    )
    parser.add_argument(
        "--extract-squashfs",
        metavar="FICHIER",
        help="Extrait les noyaux, initramfs et modules détectés depuis l'image SquashFS vers un répertoire",
    )
    parser.add_argument(
        "--extract-dir",
        metavar="RÉPERTOIRE",
        default=".",
        help="Répertoire de destination pour l'extraction (défaut: répertoire courant)",
    )
    parser.add_argument(
        "--health",
        action="store_true",
        help="Exécute une vérification complète de santé du système et affiche un rapport",
    )

    args = parser.parse_args()

    # Traitement des options de scan
    if args.scan_squashfs or args.scan_dir:
        from fsdeploy.lib.config import FsDeployConfig
        from fsdeploy.lib.modules.loader import ModuleLoader

        config = FsDeployConfig()
        # Chemin par défaut vers les scanners inclus
        scanner_path = Path(__file__).parent / "lib" / "modules" / "scanner"
        config.set("modules.paths", [str(scanner_path)])
        loader = ModuleLoader(config)
        # Charger le module squashfs
        if not loader.load_module("squashfs"):
            print("[ERREUR] Impossible de charger le module squashfs")
            sys.exit(1)
        scanner_func = loader.scanners.get("squashfs")
        if not scanner_func:
            print("[ERREUR] Scanner squashfs non enregistré")
            sys.exit(1)

        if args.scan_squashfs:
            image_path = Path(args.scan_squashfs)
            if not image_path.exists():
                print(f"[ERREUR] Fichier {image_path} introuvable")
                sys.exit(1)
            result = scanner_func(image_path)
            print(json.dumps(result, indent=2))
            sys.exit(0)

        if args.scan_dir:
            dir_path = Path(args.scan_dir)
            if not dir_path.is_dir():
                print(f"[ERREUR] Répertoire {dir_path} invalide")
                sys.exit(1)
            for item in dir_path.glob("**/*.squashfs"):
                print(f"\n=== Analyse de {item} ===")
                result = scanner_func(item)
                print(json.dumps(result, indent=2))
            sys.exit(0)

    # Vérification overlayfs
    if args.check_overlay:
        from fsdeploy.lib.overlay_check import check_all_overlays
        issues = check_all_overlays()
        if issues:
            print("⚠️  Problèmes détectés dans les overlayfs :")
            for msg in issues:
                print(f"  - {msg}")
            sys.exit(1)
        else:
            print("✅ Aucun problème détecté dans les overlayfs.")
            sys.exit(0)

    # Vérification des montages legacy
    if args.check_legacy_mounts:
        from fsdeploy.lib.legacy_mount_check import check_legacy_mounts
        issues = check_legacy_mounts()
        if issues:
            print("⚠️  Problèmes détectés dans les montages legacy :")
            for msg in issues:
                print(f"  - {msg}")
            sys.exit(1)
        else:
            print("✅ Aucun problème détecté dans les montages legacy.")
            sys.exit(0)

    # Extraction depuis une image SquashFS
    if args.extract_squashfs:
        from fsdeploy.lib.config import FsDeployConfig
        from fsdeploy.lib.modules.loader import ModuleLoader
        from pathlib import Path
        import subprocess

        config = FsDeployConfig()
        scanner_path = Path(__file__).parent / "lib" / "modules" / "scanner"
        config.set("modules.paths", [str(scanner_path)])
        loader = ModuleLoader(config)
        if not loader.load_module("squashfs"):
            print("[ERREUR] Impossible de charger le module squashfs")
            sys.exit(1)
        scanner_func = loader.scanners.get("squashfs")
        extract_func = loader.scanners.get("squashfs_extract")
        if not scanner_func or not extract_func:
            print("[ERREUR] Fonctions de scan/extraction non disponibles")
            sys.exit(1)
        image_path = Path(args.extract_squashfs)
        if not image_path.exists():
            print(f"[ERREUR] Fichier {image_path} introuvable")
            sys.exit(1)
        # D'abord scanner pour obtenir les chemins
        scan_result = scanner_func(image_path)
        # Préparer les motifs pour chaque catégorie intéressante
        categories = ["kernel", "initramfs", "modules"]
        all_paths = []
        for cat in categories:
            all_paths.extend(scan_result.get(cat, []))
        if not all_paths:
            print("[INFO] Aucun fichier pertinent trouvé à extraire.")
            sys.exit(0)
        # Extraire chaque fichier individuellement
        output_dir = Path(args.extract_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        extracted_count = 0
        for rel_path in all_paths:
            # Utiliser unsquashfs pour extraire ce fichier précis
            cmd = ["unsquashfs", "-f", "-d", str(output_dir), str(image_path), rel_path]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if proc.returncode == 0:
                print(f"  Extrait : {rel_path}")
                extracted_count += 1
            else:
                print(f"  Échec extraction de {rel_path} : {proc.stderr[:100]}")
        print(f"[INFO] {extracted_count} fichiers extraits dans {output_dir}")
        sys.exit(0)

    # Vérification de santé globale
    if args.health:
        from fsdeploy.lib.config import FsDeployConfig
        from fsdeploy.lib.modules.loader import ModuleLoader
        from pathlib import Path
        import json

        config = FsDeployConfig()
        # Chemin vers les modules de vérification (health)
        check_path = Path(__file__).parent / "lib" / "modules" / "check"
        config.set("modules.paths", [str(check_path)])
        loader = ModuleLoader(config)
        if not loader.load_module("health"):
            print("[ERREUR] Impossible de charger le module health")
            sys.exit(1)from fsdeploy.lib.scheduler.runtime import Runtime
from fsdeploy.lib.scheduler.core.scheduler import Scheduler
from fsdeploy.lib.scheduler.core.resolver import Resolver
from fsdeploy.lib.scheduler.core.executor import Executor

def main():
    runtime = Runtime()
    scheduler = Scheduler(Resolver(), Executor(), runtime)
    Scheduler._global_instance = scheduler  # Définir le singleton
    app = FsDeployApp(runtime=runtime)  # ✅ Passer runtime
    app.run()
        health_func = loader.scanners.get("health")
        if not health_func:
            print("[ERREUR] Scanner health non enregistré")
            sys.exit(1)
        print("[INFO] Exécution des vérifications de santé...")
        report = health_func(verbose=True)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        # Déterminer un code de sortie en fonction de l'état global
        if report.get("overall", {}).get("status") == "ok":
            sys.exit(0)
        else:
            sys.exit(1)

    # Configuration de la persistance des logs si demandée
    if args.log_persist:
        from fsdeploy.lib.scheduler.intentlog.persistent import PersistentRecordStore
        from fsdeploy.lib.scheduler.intentlog.log import intent_log

        # Remplacer le store par défaut par un store persistant
        intent_log.store = PersistentRecordStore(args.log_persist)
        print(f"[INFO] Persistance des logs activée vers {args.log_persist}")
        
    runtime = Runtime()
    scheduler = Scheduler(Resolver(), Executor(), runtime)
    Scheduler._global_instance = scheduler  # Définir le singleton
    app = FsDeployApp(runtime=runtime)  # ✅ Passer runtime

    app.run()


if __name__ == "__main__":
    main()
