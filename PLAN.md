## 📄 **PLAN.md — fsdeploy (Branche `dev`)**

*Dernière mise à jour : 14 avril 2026*

---

### ✅ **Tâches Terminées (7.0–7.12)**

*(Conservées pour référence : étapes 7.0 à 7.12 validées et terminées.)*

---

---

### 🔴 **Tâches Restantes (Priorité)**


| **Étape** | **Problème**                                                                      | **Tâche**                                                                                            | **Fichiers Concernés**                                                               | **Statut**               |
| --------- | --------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ | ------------------------ |
| **7.13**  | La configuration (`FsDeployConfig`) n’est **pas encore validée** dans les écrans. | **Finaliser la configuration et l’utilisation dans `ModuleRegistryScreen**`.                         | `fsdeploy/__main__.py`, `fsdeploy/lib/ui/screens/module_registry.py`                 | ⏳ **À faire avant 7.14** |
| **7.14**  | Le `bridge` n’est **pas validé ni utilisé correctement** dans les écrans.         | **Vérifier et valider l’accès à `self.app.bridge**` dans tous les écrans (ex: `CrossCompileScreen`). | **Tous les écrans** (`CrossCompileScreen`, `ModuleRegistryScreen`, etc.)             | ⏳ **À faire maintenant** |
| **7.15**  | Documentation manquante pour `contrib/`.                                          | **Ajouter une section dans `CONTRIBUTING.md**` expliquant l’organisation de `fsdeploy/contrib/`.     | `CONTRIBUTING.md`                                                                    | ⏳                        |
| **7.16**  | Permissions incorrectes sur les scripts init.                                     | **Vérifier et corriger les permissions** : `chmod +x` pour OpenRC, `chmod 644` pour systemd.         | `fsdeploy/contrib/openrc/fsdeploy.init`, `fsdeploy/contrib/systemd/fsdeploy.service` | ⏳                        |


---

## 📄 **add.md — Étape 7.14 : Fichiers à modifier pour valider `self.app.bridge**`

---

### **📌 Problème Identifié**

Le `bridge` n’est **ni validé ni utilisé correctement** dans les écrans (`CrossCompileScreen`, `ModuleRegistryScreen`, etc.).

---

### **📌 Fichiers à modifier (par ordre de priorité)**


| **Fichier**                                       | **Action requise**                                                                       | **Méthodes/Classes à vérifier**            |
| ------------------------------------------------- | ---------------------------------------------------------------------------------------- | ------------------------------------------ |
| **Tous les écrans** (`fsdeploy/lib/ui/screens/`)  | **Vérifier et corriger l’accès à `self.app.bridge**` dans chaque écran.                  | `__init__`, `on_activate`, `on_deactivate` |
| `fsdeploy/__main__.py`                            | **S’assurer que `FsDeployApp` initialise et passe `self.bridge**` à tous les écrans.     | `FsDeployApp.__init__`                     |
| `fsdeploy/lib/ui/screens/cross_compile_screen.py` | **Valider l’utilisation de `self.app.bridge**` dans les méthodes critiques.              | `on_activate`, `compile`, `clean`          |
| `fsdeploy/lib/ui/screens/module_registry.py`      | **Vérifier que `self.app.bridge` est accessible** dans l’initialisation et les méthodes. | `__init__`, `load_modules`                 |
