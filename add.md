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


