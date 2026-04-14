# **PLAN.md — fsdeploy (Branche `dev`)**

*Dernière mise à jour : 2026-04-13*

---

---

## ✅ **Tâches Terminées (7.0–7.12)**


| **Étape** | **Description**                                                                             | **Statut** | **Fichiers Validés**                       |
| --------- | ------------------------------------------------------------------------------------------- | ---------- | ------------------------------------------ |
| **7.0**   | `launch.sh` : Branche `dev` par défaut + options `--run/--no-run` ajoutées.                 | ✅          | `launch.sh`                                |
| **7.1**   | `live/setup.py` : Correction de l’initialisation des `linux-headers` via `uname -r`.        | ✅          | `live/setup.py`                            |
| **7.2**   | Sync des écrans dans `tests/` (stale copies) → Fichiers corrigés.                           | ✅          | `tests/`                                   |
| **7.4**   | README.md : Mise à jour des instructions d’installation pour `dev`.                         | ✅          | `README.md`                                |
| **7.5**   | DIAGRAMS.md : Correction des chemins `linux-headers`.                                       | ✅          | `DIAGRAMS.md`                              |
| **7.6**   | `fsdeploy_main_status.md` : Suppression (obsolète).                                         | ✅          | `fsdeploy_main_status.md`                  |
| **7.7**   | `fsdeploy/lib/function/module/registry.py` : Re-export corrigé.                             | ✅          | `fsdeploy/lib/function/module/registry.py` |
| **7.8**   | Supprimer `tests/fsdeploy/` (29 fichiers dupliqués).                                        | ✅          | `tests/fsdeploy/`                          |
| **7.9**   | Nettoyer et centraliser `contrib/` dans `fsdeploy/contrib/`.                                | ✅          | `contrib/`, `fsdeploy/contrib/`            |
| **7.10**  | Supprimer `lib/ui/` à la racine (redondant).                                                | ✅          | `lib/ui/`                                  |
| **7.11**  | Ajouter `global_instance()` à `Scheduler` pour résoudre le problème du `bridge`.            | ✅          | `fsdeploy/lib/scheduler/core/scheduler.py` |
| **7.12**  | Initialiser `Runtime` et `FsDeployConfig` dans `__main__.py` et les passer à `FsDeployApp`. | ✅          | `fsdeploy/__main__.py`                     |


---

---

## 🔴 **Tâches Restantes (Priorité)**


| **Étape** | **Problème**                                                     | **Tâche**                                                                                                   | **Fichiers Concernés**                                                               | **Statut**               |
| --------- | ---------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ | ------------------------ |
| **7.13**  | La config (`FsDeployConfig`) n’est pas utilisée dans les écrans. | **Passer `self.app.config**` aux écrans (ex: `ModuleRegistryScreen`).                                       | `fsdeploy/__main__.py`, `fsdeploy/lib/ui/screens/module_registry.py`                 | ⏳ **À faire maintenant** |
| **7.14**  | Validation du `bridge` dans les écrans.                          | **Vérifier que `self.app.bridge` fonctionne** dans tous les écrans (ex: `CrossCompileScreen`).              | Tous les écrans (`CrossCompileScreen`, `ModuleRegistryScreen`)                       | ⏳                        |
| **7.15**  | Documentation manquante pour `contrib/`.                         | **Ajouter une section dans `CONTRIBUTING.md**` : organisation de `fsdeploy/contrib/` (OpenRC/systemd/test). | `CONTRIBUTING.md`                                                                    | ⏳                        |
| **7.16**  | Permissions incorrectes sur les scripts init.                    | **Vérifier/corriger les permissions** : `chmod +x` pour OpenRC, `chmod 644` pour systemd.                   | `fsdeploy/contrib/openrc/fsdeploy.init`, `fsdeploy/contrib/systemd/fsdeploy.service` | ⏳                        |