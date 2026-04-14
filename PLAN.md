---

## 📄 **add.md — Étape 7.13 : Configurer et utiliser `FsDeployConfig**`

---

### **📌 Problème Identifié**

La configuration (`FsDeployConfig`) n’est **pas passée aux écrans**, ce qui empêche les écrans d’accéder aux paramètres de configuration (ex: `pool.boot_pool`).

---

### **📌 Instructions à Suivre**

1. **Configurer `FsDeployConfig` dans `fsdeploy/__main__.py**` :
  - Initialiser `FsDeployConfig.default()` et le passer à `FsDeployApp`.
2. **Mettre à jour `fsdeploy/lib/ui/screens/module_registry.py**` :
  - Utiliser `self.app.config` dans l’initialisation de l’écran pour accéder à la configuration.
3. **Vérifier les imports dans les écrans** :
  - Remplacer les appels directs à la configuration par `self.app.config.get(...)`.