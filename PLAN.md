# **PLAN.md — fsdeploy (Branche `dev`)**

*Dernière mise à jour : 2026-04-13*  
*État après mise à jour du dépôt et prochaines étapes à réaliser.*

---

---

## ✅ **Tâches Terminées (7.0–7.10)**


| **Étape** | **Description**                                                                      | **Statut** | **Validation**                                                |
| --------- | ------------------------------------------------------------------------------------ | ---------- | ------------------------------------------------------------- |
| **7.0**   | `launch.sh` : Branche `dev` par défaut + options `--run/--no-run` ajoutées.          | ✅          | Fichier modifié et testé.                                     |
| **7.1**   | `live/setup.py` : Correction de l’initialisation des `linux-headers` via `uname -r`. | ✅          | Fichier modifié et testé.                                     |
| **7.2**   | Sync des écrans dans `tests/` (stale copies) → Fichiers corrigés.                    | ✅          | Fichiers mis à jour.                                          |
| **7.4**   | README.md : Mise à jour des instructions d’installation pour `dev`.                  | ✅          | Fichier modifié et validé.                                    |
| **7.5**   | DIAGRAMS.md : Correction des chemins `linux-headers`.                                | ✅          | Fichier modifié.                                              |
| **7.6**   | `fsdeploy_main_status.md` : Suppression (obsolète).                                  | ✅          | Fichier supprimé.                                             |
| **7.7**   | `fsdeploy/lib/function/module/registry.py` : Re-export corrigé.                      | ✅          | Fichier mis à jour.                                           |
| **7.8**   | Supprimer `tests/fsdeploy/` (29 fichiers dupliqués).                                 | ✅          | Dossier supprimé.                                             |
| **7.9**   | Nettoyer et centraliser `contrib/` dans `fsdeploy/contrib/`.                         | ✅          | Dossier nettoyé, fichiers OpenRC/systemd centralisés.         |
| **7.10**  | Supprimer `lib/ui/` à la racine (redondant).                                         | ✅          | Dossier supprimé, aucun import depuis `lib.ui.*` ne subsiste. |


---

---

## 🔴 **Tâches Restantes (Priorité)**


| **Étape** | **Problème**                                                           | **Tâche**                                                                     | **Fichiers Concernés**                                                               | **Statut**               |
| --------- | ---------------------------------------------------------------------- | ----------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ | ------------------------ |
| **7.11**  | `Scheduler` n’a pas de `global_instance()` → `bridge` non fonctionnel. | **Ajouter `global_instance()**` à `fsdeploy/lib/scheduler/core/scheduler.py`. | `fsdeploy/lib/scheduler/core/scheduler.py`                                           | ⏳ **À faire maintenant** |
| **7.12**  | `__main__.py` ne passe pas `runtime` → `self.bridge = None`.           | **Initialiser `Runtime` et `FsDeployConfig**` dans `__main__.py`.             | `fsdeploy/__main__.py`                                                               | ⏳                        |
| **7.13**  | La config (`FsDeployConfig`) n’est pas utilisée dans les écrans.       | **Passer `self.app.config**` aux écrans (ex: `ModuleRegistryScreen`).         | `fsdeploy/lib/ui/screens/module_registry.py`                                         | ⏳                        |
| **7.14**  | Le `bridge` ne fonctionne dans aucun écran.                            | **Valider que `self.app.bridge` est fonctionnel**.                            | Tous les écrans                                                                      | ⏳                        |
| **7.15**  | Documentation manquante pour `contrib/`.                               | **Ajouter une section dans `CONTRIBUTING.md**`.                               | `CONTRIBUTING.md`                                                                    | ⏳                        |
| **7.16**  | Permissions incorrectes sur les scripts init.                          | **Vérifier/corriger les permissions**.                                        | `fsdeploy/contrib/openrc/fsdeploy.init`, `fsdeploy/contrib/systemd/fsdeploy.service` | ⏳                        |