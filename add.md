## 📄 **add.md — Prochaine Tâche : 7.15 ou 7.16**

*(À adapter selon la priorité choisie.)*

---

### **📌 Si 7.15 est prioritaire (Documentation `contrib/`)**

---

#### **Fichiers à éditer :**


| **Fichier**       | **Action requise**                                                        | **Contenu à ajouter**                                        |
| ----------------- | ------------------------------------------------------------------------- | ------------------------------------------------------------ |
| `CONTRIBUTING.md` | **Ajouter une section** expliquant l’organisation de `fsdeploy/contrib/`. | - Description des dossiers (`openrc/`, `systemd/`, `test/`). |
| &nbsp;            | &nbsp;                                                                    | - Instructions pour ajouter un script/init (ex: `chmod +x`). |
| &nbsp;            | &nbsp;                                                                    | - Exemple de structure et de bonnes pratiques.               |


---

#### **Instructions rapides :**

1. **Ouvrir `CONTRIBUTING.md**`.
2. **Ajouter une section** :
  ```markdown
   ## 📁 Organisation de `fsdeploy/contrib/`
   - `openrc/` : Scripts de démarrage pour OpenRC (ex: `fsdeploy.init`).
   - `systemd/` : Fichiers de service systemd (ex: `fsdeploy.service`).
   - `test/` : Scripts et configurations pour tester les contributions.
  ```
3. **Valider le format** avec les titres et listes à puces.

---

---

### **📌 Si 7.16 est prioritaire (Permissions des scripts init)**

---

#### **Fichiers à éditer :**


| **Fichier**                                 | **Action requise**                                   | **Commande pour corriger**                            |
| ------------------------------------------- | ---------------------------------------------------- | ----------------------------------------------------- |
| `fsdeploy/contrib/openrc/fsdeploy.init`     | **Rendre exécutable** (`chmod +x`).                  | `chmod +x fsdeploy/contrib/openrc/fsdeploy.init`      |
| `fsdeploy/contrib/systemd/fsdeploy.service` | **Mettre en lecture seule pour tous** (`chmod 644`). | `chmod 644 fsdeploy/contrib/systemd/fsdeploy.service` |


---

#### **Instructions rapides :**

1. **Vérifier les permissions actuelles** :
  ```bash
   ls -l fsdeploy/contrib/openrc/fsdeploy.init
   ls -l fsdeploy/contrib/systemd/fsdeploy.service
  ```
2. **Appliquer les corrections** :
  ```bash
   chmod +x fsdeploy/contrib/openrc/fsdeploy.init
   chmod 644 fsdeploy/contrib/systemd/fsdeploy.service
  ```
3. **Valider** :
  - Relancer les tests pour s’assurer que les scripts init fonctionnent.

---

---

**Prochaine étape** :

- **Si 7.15 est prioritaire** : Rédige la section `contrib/` dans `CONTRIBUTING.md`.
- **Si 7.16 est prioritaire** : Corrige les permissions des scripts init.

**Dis-moi ce que tu veux faire en priorité, et je t’aide à avancer !** 🚀
