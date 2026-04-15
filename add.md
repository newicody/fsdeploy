### **📄 add.md — Préparation de la suite**

---

### **📌 Prochaine tâche (7.18 ou nouvelle itération) :**

*(À définir selon tes besoins)*

---

#### **Options possibles :**


| **Option**                       | **Description**                                                                        | **Fichiers à préparer**                                              |
| -------------------------------- | -------------------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| **7.18 : Ajouter un CHANGELOG**  | Documenter les changements apportés par les étapes 7.13 à 7.17 dans `CHANGELOG.md`.    | `CHANGELOG.md`                                                       |
| **7.18 : Améliorer la sécurité** | Ajouter des validations supplémentaires dans le scheduler (ex: limites de ressources). | `fsdeploy/lib/scheduler/core/scheduler.py`, `fsdeploy/lib/config.py` |
| **7.18 : Optimiser les logs**    | Centraliser les logs et ajouter des niveaux de log (debug, info, warning, error).      | `fsdeploy/__main__.py`, `fsdeploy/lib/logging/...`                   |
| **7.18 : Préparer une release**  | Préparer les fichiers pour une release (ex: `setup.py`, `README.md`, `CHANGELOG.md`).  | `setup.py`, `README.md`, `CHANGELOG.md`, `MANIFEST.in`               |


---

#### **Fichiers à éditer selon l’option choisie :**

*(Exemple pour un CHANGELOG)*


| **Fichier**    | **Action requise**                                                                   |
| -------------- | ------------------------------------------------------------------------------------ |
| `CHANGELOG.md` | **Ajouter une section** pour les étapes 7.13 à 7.17 :                                |
| &nbsp;         | ```markdown                                                                          |
| &nbsp;         | ## [1.0.0] - 2026-04-15                                                              |
| &nbsp;         | ### Ajouté                                                                           |
| &nbsp;         | - Validation de `FsDeployConfig` dans `ModuleRegistryScreen`.                        |
| &nbsp;         | - Accès à `self.app.bridge` dans tous les écrans.                                    |
| &nbsp;         | - Documentation de `fsdeploy/contrib/`.                                              |
| &nbsp;         | - Correction des permissions des scripts init (`fsdeploy.init`, `fsdeploy.service`). |
| &nbsp;         | ```                                                                                  |


---

### **📌 Instructions rapides :**

1. **Choisis une option** pour la prochaine itération (7.18).
2. **Prépare les fichiers** nécessaires (ex: `CHANGELOG.md`).
3. **Documente les changements** pour faciliter la maintenance.

---

---

**Prochaine étape :**  
**Quelle option veux-tu choisir pour la prochaine itération ?**  
Dis-moi ce que tu veux faire, et je t’aide à préparer les fichiers ! 🚀
