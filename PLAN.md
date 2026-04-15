## 📄 **PLAN.md — fsdeploy (Branche `dev`)**

*Dernière mise à jour : 15 avril 2026*

---

### ✅ **Tâches Terminées (7.0–7.12)**

*(Conservées pour référence et historique.)*


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


| **Étape** | **Problème**                                                                           | **Tâche**                                                                                  | **Fichiers Concernés**                                                               | **Statut**               |
| --------- | -------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------ | ------------------------ |
| **7.13**  | La configuration (`FsDeployConfig`) n’est **pas validée** dans `ModuleRegistryScreen`. | **Valider l’utilisation de `self.app.config**` dans `ModuleRegistryScreen`.                | `fsdeploy/__main__.py`, `fsdeploy/lib/ui/screens/module_registry.py`                 | 🟡 **À valider**         |
| **7.14**  | Le `bridge` n’est **pas validé** dans les écrans.                                      | **Valider l’accès à `self.app.bridge**` dans tous les écrans (`CrossCompileScreen`, etc.). | Tous les écrans (`fsdeploy/lib/ui/screens/`)                                         | 🟡 **À valider**         |
| **7.15**  | Documentation manquante pour `contrib/`.                                               | **Ajouter une section dans `CONTRIBUTING.md**` pour `fsdeploy/contrib/`.                   | `CONTRIBUTING.md`                                                                    | ⏳ **À faire maintenant** |
| **7.16**  | **Permissions incorrectes** sur les scripts init (`OpenRC`, `systemd`).                | **Corriger les permissions** : `chmod +x` pour OpenRC, `chmod 644` pour systemd.           | `fsdeploy/contrib/openrc/fsdeploy.init`, `fsdeploy/contrib/systemd/fsdeploy.service` | ⏳ **À faire maintenant** |
| **7.17**  | **Intégration globale** : Vérifier que toutes les corrections sont cohérentes.         | **Tester l’intégration** des étapes 7.13 à 7.16.                                           | Tous les fichiers modifiés                                                           | ⏳ **Préparation**        |


---
