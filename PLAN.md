# **PLAN — fsdeploy (Branche `dev`)**
*Dernière mise à jour : 2026-04-13*

---

---

## ✅ **7.0–7.8 : Tâches Terminées**
- [x] **7.0** `launch.sh` : Branche `dev` par défaut + options `--run/--no-run`.
- [x] **7.1** `live/setup.py` : Correction de l’initialisation des `linux-headers` via `uname -r`.
- [x] **7.2** Sync des écrans dans `tests/` (stale copies) → Fichiers corrigés.
- [x] **7.4** README.md : Mise à jour des instructions d’installation pour `dev`.
- [x] **7.5** DIAGRAMS.md : Correction des chemins `linux-headers`.
- [x] **7.6** `fsdeploy_main_status.md` : Suppression (obsolète).
- [x] **7.7** `fsdeploy/lib/function/module/registry.py` : Re-export corrigé.
- [x] **7.8** **Supprimer `tests/fsdeploy/`** → Fait ✅.

---

---

## 🔴 **7.9–7.16 : Tâches Restantes (Priorité)**

---

### **📌 7.9 : Nettoyer et centraliser les dossiers `contrib/`**
**Problème** :
- **`contrib/` à la racine** contient des scripts **sysvinit/upstart** obsolètes (peu utilisés aujourd’hui).
- **`fsdeploy/contrib/`** contient des scripts **OpenRC/systemd** modernes.
- **Redondance** : Les fichiers dans `contrib/sysvinit/fsdeploy` et `contrib/upstart/fsdeploy.conf` font doublon avec ceux dans `fsdeploy/contrib/openrc/` et `fsdeploy/contrib/systemd/`.

**Tâches** :
- Centraliser tous les fichiers utiles dans `fsdeploy/contrib/` :
  - Déplacer les scripts de test (`test_*.sh`) de `contrib/integration/` vers `fsdeploy/contrib/integration/`.
  - Déplacer les scripts OpenRC (`fsdeploy.init`, `fsdeploy.initd`) dans `fsdeploy/contrib/openrc/`.
  - Déplacer le service systemd (`fsdeploy.service`) dans `fsdeploy/contrib/systemd/`.
- Supprimer les fichiers redondants :
  - `contrib/sysvinit/fsdeploy` (sysvinit obsolète).
  - `contrib/upstart/fsdeploy.conf` (upstart obsolète).
- Supprimer le dossier `contrib/` à la racine.

---
---
### **📌 7.10 : Supprimer la redondance dans `lib/ui/`**
**Problème** :
- Le dossier **`lib/ui/` à la racine** contient un seul fichier (`mixins.py`) redondant (fonctionnalités déjà dans `fsdeploy/lib/ui/`).

**Tâches** :
- Supprimer le dossier `lib/ui/` à la racine.

---
---
### **🛠️ Problèmes d’Initialisation et de Configuration**

---

### **📌 7.11 : Corriger l’initialisation du `Scheduler`**
**Problème** :
- Le `Scheduler` n’a **pas de méthode `global_instance()`**, donc le `SchedulerBridge` ne peut pas accéder au `Scheduler` global.
- Résultat : Le `bridge` ne fonctionne pas, et tous les écrans ont `self.app.bridge = None`.

**Tâches** :
- Ajouter `global_instance()` à la classe `Scheduler` dans `fsdeploy/lib/scheduler/core/scheduler.py`.

---
---
### **📌 7.12 : Initialiser le `Runtime` et le passer à `FsDeployApp`**
**Problème** :
- Le `__main__.py` ne passe **pas `runtime`** à `FsDeployApp` → `self.bridge = None`.
- Résultat : Le `bridge` n’est pas disponible dans les écrans.

**Tâches** :
- Initialiser le `Runtime` dans `__main__.py`.
- Passer le `Runtime` et la `config` à `FsDeployApp`.

---
---
### **📌 7.13 : Configurer `FsDeployConfig` et l’utiliser dans les écrans**
**Problème** :
- La configuration (`FsDeployConfig`) n’est **pas passée aux écrans**.
- Résultat : Les écrans ne peuvent pas accéder aux paramètres de configuration.

**Tâches** :
- Passer `FsDeployConfig.default()` à `FsDeployApp`.
- Utiliser `self.app.config` dans les écrans (ex: `ModuleRegistryScreen`) pour accéder aux paramètres.

---
---
### **📌 7.14 : Valider le fonctionnement du `bridge`**
**Problème** :
- Le `bridge` ne fonctionne dans **aucun écran** → Erreur "bridge non disponible".

**Tâches** :
- Vérifier que `FsDeployApp` a un `bridge` fonctionnel.
- Tester un écran (ex: `CrossCompileScreen`) pour confirmer que le `bridge` fonctionne.

---
---
## **📌 Tâches Secondaires (À Faire Après les Corrections Critiques)**

---

### **📌 7.15 : Mettre à jour la documentation**
**Problème** :
- Il n’y a **pas de guideline** pour placer les nouveaux scripts d’init.

**Tâches** :
- Ajouter une section dans `CONTRIBUTING.md` ou `README.md` expliquant :
  - Où placer les scripts OpenRC/systemd (`fsdeploy/contrib/`).
  - Où placer les scripts de test (`fsdeploy/contrib/integration/`).
  - Pourquoi éviter `contrib/` à la racine.

---
---
### **📌 7.16 : Vérifier les permissions des scripts**
**Problème** :
- Certains scripts init n’ont peut-être **pas les bonnes permissions**.

**Tâches** :
- Vérifier et corriger les permissions :
  - Scripts OpenRC : `chmod +x`.
  - Fichiers systemd : `chmod 644`.

---
---
## 📋 **Checklist Globale (À Cocher Après Validation)**
- [x] **7.8** : `tests/fsdeploy/` supprimé.
- [ ] **7.9** : `contrib/` centralisé dans `fsdeploy/contrib/`, fichiers redondants supprimés.
- [ ] **7.10** : `lib/ui/` supprimé à la racine.
- [ ] **7.11** : `global_instance()` ajouté à `Scheduler`.
- [ ] **7.12** : `Runtime` et `FsDeployConfig` initialisés dans `__main__.py`.
- [ ] **7.13** : La config est utilisée dans les écrans.
- [ ] **7.14** : Le `bridge` fonctionne dans tous les écrans.
- [ ] **7.15** : Documentation mise à jour (`CONTRIBUTING.md`).
- [ ] **7.16** : Permissions des scripts vérifiées/corrigées.