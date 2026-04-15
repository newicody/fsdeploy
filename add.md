## 📄 **add.md — Prochaine Tâche : 7.16**

*(Corriger les permissions des scripts init)*

---

### **📌 Problème Identifié**

Les scripts init (`fsdeploy.init`, `fsdeploy.service`) ont des **permissions incorrectes** :

- `fsdeploy.init` doit être **exécutable** (`chmod +x`).
- `fsdeploy.service` doit être en **lecture seule pour tous** (`chmod 644`).

---

### **📌 Fichiers à éditer**


| **Fichier**                                 | **Action requise**                                   | **Commande pour corriger**                            |
| ------------------------------------------- | ---------------------------------------------------- | ----------------------------------------------------- |
| `fsdeploy/contrib/openrc/fsdeploy.init`     | **Rendre exécutable** (`chmod +x`).                  | `chmod +x fsdeploy/contrib/openrc/fsdeploy.init`      |
| `fsdeploy/contrib/systemd/fsdeploy.service` | **Mettre en lecture seule pour tous** (`chmod 644`). | `chmod 644 fsdeploy/contrib/systemd/fsdeploy.service` |


---

### **📌 Instructions rapides**

1. **Vérifier les permissions actuelles** :
  ```bash
   ls -l fsdeploy/contrib/openrc/fsdeploy.init
   ls -l fsdeploy/contrib/systemd/fsdeploy.service
  ```
  - **Attendu pour `fsdeploy.init**` : `-rwxr-xr-x` (755).
  - **Attendu pour `fsdeploy.service**` : `-rw-r--r--` (644).
2. **Appliquer les corrections** :
  ```bash
   chmod +x fsdeploy/contrib/openrc/fsdeploy.init
   chmod 644 fsdeploy/contrib/systemd/fsdeploy.service
  ```
3. **Valider** :
  - Relancer les tests pour s’assurer que les scripts init fonctionnent correctement.

---

---

**Prochaine étape** :  
**Applique les corrections de permissions sur les deux fichiers init.**

**Besoin d’aide pour valider les changements ?** 🚀
