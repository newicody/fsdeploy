## 📄 **PLAN.md — fsdeploy (Branche `dev`)**

*Dernière mise à jour : 14 avril 2026*

---

---

### ✅ **Tâches Terminées (7.0–7.12)**

*(Conservées et visibles pour référence : étapes 7.0 à 7.12 validées et terminées.)*


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

### 🔴 **Tâches Restantes (Priorité)**


| **Étape** | **Problème**                                                                                         | **Tâche**                                                                                    | **Fichiers Concernés**                                                               | **Statut**               |
| --------- | ---------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ | ------------------------ |
| **7.13**  | La configuration (`FsDeployConfig`) n’est **pas encore validée** dans les écrans.                    | Finaliser la configuration et l’utilisation dans `ModuleRegistryScreen`.                     | `fsdeploy/__main__.py`, `fsdeploy/lib/ui/screens/module_registry.py`                 | 🟡 **En cours**          |
| **7.14**  | Le `bridge` n’est **pas validé ni utilisé correctement** dans les écrans.                            | Vérifier et valider l’accès à `self.app.bridge` dans tous les écrans.                        | Tous les écrans (`CrossCompileScreen`, `ModuleRegistryScreen`, etc.)                 | ⚠️ **À valider**         |
| **7.15**  | Documentation manquante pour `contrib/`.                                                             | Ajouter une section dans `CONTRIBUTING.md` expliquant l’organisation de `fsdeploy/contrib/`. | `CONTRIBUTING.md`                                                                    | ⚠️ **À valider**         |
| **7.16**  | **Permissions incorrectes** sur les scripts init (`OpenRC`, `systemd`).                              | Vérifier et corriger les permissions : `chmod +x` pour OpenRC, `chmod 644` pour systemd.     | `fsdeploy/contrib/openrc/fsdeploy.init`, `fsdeploy/contrib/systemd/fsdeploy.service` | ⏳ **À faire maintenant** |
| **7.17**  | **Intégration finale** : Vérifier que toutes les corrections sont bien appliquées et fonctionnelles. | Tester et valider l’intégration globale des étapes 7.13 à 7.16.                              | Tous les fichiers et écrans modifiés.                                                | ⏳ **À faire**            |


---
