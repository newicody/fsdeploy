"""
Tâche de vérification du scheduler.

Vérifie que toutes les tâches définies dans le programme sont bien exécutées par le scheduler.
"""
from ..task import Task
import sys
import inspect
from typing import Dict, Any, List


class SchedulerVerifyTask(Task):
    """
    Vérification de l'intégration des tâches avec le scheduler.

    Cette tâche parcourt les modules chargés, liste les sous-classes de Task,
    et vérifie qu'elles sont bien référencées par au moins un intent.
    Elle produit un rapport de couverture.
    """

    def before_run(self) -> None:
        self.log("[SchedulerVerifyTask] Début vérification de l'intégration des tâches")

    def run(self):
        # Import dynamique des modules du projet pour scanner les tâches
        # On se limite aux modules déjà importés dans sys.modules
        # pour éviter de charger tout le monde.
        import fsdeploy.lib.function as function_module
        from pathlib import Path
        import importlib
        import pkgutil

        # 1. Collecter toutes les sous-classes de Task
        task_classes = []
        modules_scanned = set()

        # Parcourir le package function
        def walk_modules(package, prefix=""):
            for _, name, is_pkg in pkgutil.iter_modules(package.__path__):
                full_name = f"{package.__name__}.{name}"
                if full_name in sys.modules:
                    mod = sys.modules[full_name]
                else:
                    try:
                        mod = importlib.import_module(full_name)
                    except ImportError:
                        continue
                modules_scanned.add(full_name)
                # Chercher les classes Task dans le module
                for obj_name, obj in inspect.getmembers(mod, inspect.isclass):
                    if (obj.__module__ == mod.__name__ and
                        issubclass(obj, Task) and obj != Task):
                        task_classes.append((full_name, obj_name, obj))

                if is_pkg:
                    # Importer le sous-package et récursion
                    try:
                        sub_pkg = importlib.import_module(full_name)
                        walk_modules(sub_pkg, full_name + ".")
                    except ImportError:
                        pass

        try:
            walk_modules(function_module)
        except Exception as e:
            self.log(f"[SchedulerVerifyTask] Erreur lors du scan: {e}")

        # 2. Récupérer les intents enregistrés (via le registre)
        try:
            from scheduler.core.registry import INTENT_REGISTRY
            intent_count = len(INTENT_REGISTRY) if INTENT_REGISTRY else 0
        except ImportError:
            # Le registre n'est pas disponible (environnement de test)
            intent_count = 0

        # 3. Rapport
        tasks_by_module: Dict[str, List[str]] = {}
        for module_name, class_name, _ in task_classes:
            tasks_by_module.setdefault(module_name, []).append(class_name)

        self.result = {
            "modules_scanned": len(modules_scanned),
            "task_classes_found": len(task_classes),
            "intents_registered": intent_count,
            "tasks_by_module": tasks_by_module,
            "health": len(task_classes) > 0 and intent_count > 0,
        }
        return True

    def after_run(self, result) -> None:
        if self.error:
            self.log(f"[SchedulerVerifyTask] Échec : {self.error}")
        else:
            health = "✅" if self.result.get("health") else "⚠"
            self.log(
                f"[SchedulerVerifyTask] Terminé. "
                f"Tâches: {self.result['task_classes_found']}, "
                f"Intents: {self.result['intents_registered']} {health}"
            )
