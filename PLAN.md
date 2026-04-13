# **PLAN — fsdeploy (Branche `dev`)**
*Dernière mise à jour : 2026-04-13*
*Objectif : Résoudre tous les problèmes de duplication, de configuration, et d’initialisation identifiés dans le projet.*

---

---

## ✅ **7.0–7.8 : Tâches Terminées**
- [x] **7.0** `launch.sh` : Branche `dev` par défaut + options `--run/--no-run` ajoutées.
- [x] **7.1** `live/setup.py` : Correction de l’initialisation des `linux-headers` via `uname -r`.
- [x] **7.2** Sync des écrans dans `tests/` (stale copies) → Fichiers corrigés.
- [x] **7.4** README.md : Mise à jour des instructions d’installation pour `dev`.
- [x] **7.5** DIAGRAMS.md : Correction des chemins `linux-headers`.
- [x] **7.6** `fsdeploy_main_status.md` : Suppression (obsolète).
- [x] **7.7** `fsdeploy/lib/function/module/registry.py` : Re-export corrigé.
- [x] **7.8** **Supprimer `tests/fsdeploy/`** → Fait ✅ (29 fichiers supprimés, plus de duplication).
- [x] **7.9** `contrib/` nettoyé et centralisé dans `fsdeploy/contrib/`.

---

---

## 🔴 **7.10–7.16 : Tâches Restantes (Priorité Absolue)**

### **📌 7.10 : Supprimer la redondance dans `lib/ui/`**
**Problème** :
- Le dossier **`lib/ui/` à la racine** contient un seul fichier (`mixins.py`) redondant (fonctionnalités déjà dans `fsdeploy/lib/ui/`).

**Tâches** :
- Supprimer le dossier `lib/ui/`.

---
---
### **🛠️ Problèmes d’Initialisation et de Configuration**

---

### **📌 7.11 : Corriger l’initialisation du `Scheduler`**
**Problème** :
- Le `Scheduler` n’a **pas de méthode `global_instance()`**, donc le `SchedulerBridge` ne peut pas accéder au `Scheduler` global.
- Résultat : Le `bridge` ne fonctionne pas → **"bridge non disponible"** dans tous les écrans.

**Tâches** :
- Ajouter `global_instance()` à la classe `Scheduler` dans `fsdeploy/lib/scheduler/core/scheduler.py`.

---
---
### **📌 7.12 : Initialiser le `Runtime` et le passer à `FsDeployApp`**
**Problème** :
- Le `__main__.py` ne passe **pas `runtime`** à `FsDeployApp` → `self.bridge = None`.

**Tâches** :
- Initialiser le `Runtime` dans `__main__.py`.
- Passer le `Runtime` et la `config` à `FsDeployApp`.

---
---
### **📌