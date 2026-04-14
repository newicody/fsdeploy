# **add.md — Étape 7.13 : Configurer `FsDeployConfig` et l’utiliser dans les écrans**

*Date : 2026-04-13*

---

---

## **📌 Problème Identifié**

La configuration (`FsDeployConfig`) n’est **pas passée aux écrans**, donc les écrans ne peuvent pas accéder aux paramètres de configuration (ex: `pool.boot_pool`).

---

---

## **📌 Tâches à Réaliser**

1. **Passer `FsDeployConfig.default()` à `FsDeployApp**` :
  ```python
   # Dans fsdeploy/__main__.py
   from fsdeploy.lib.config import FsDeployConfig

   def main():
       runtime = get_global_runtime()
       config = FsDeployConfig.default()  # Initialiser la config
       scheduler = Scheduler(Resolver(), Executor(), runtime)
       Scheduler._global_instance = scheduler
       app = FsDeployApp(runtime=runtime, config=config)  # Passer la config
       app.run()
  ```
2. **Utiliser `self.app.config` dans `ModuleRegistryScreen**` :
  ```python
   # Dans fsdeploy/lib/ui/screens/module_registry.py
   def __init__(self, *args, **kwargs):
       super().__init__(*args, **kwargs)
       self.registry = ModuleRegistry(self.app.config)  # Utiliser la config
  ```
3. **Mettre à jour les imports dans les écrans** :
  - Remplacer les appels directs à la config par `self.app.config.get(...)`.

---

---

## **📂 Fichiers Concernés**


| **Chemin**                                   | **Type**       | **Modification Requise**                    |
| -------------------------------------------- | -------------- | ------------------------------------------- |
| `fsdeploy/__main__.py`                       | Initialisation | Ajouter `config=FsDeployConfig.default()`.  |
| `fsdeploy/lib/ui/screens/module_registry.py` | Écran          | Utiliser `self.app.config` dans `__init__`. |


---

---

## **🔍 Validation Après Correction**

1. **Vérifier que la config est accessible** :
  ```bash
   python -c "from fs
  ```
