## 📄 **add.md — Prochaine Tâche : 7.17**

*(Tester l’intégration globale des corrections 7.13 à 7.16)*

---

### **📌 Problème Identifié**

Toutes les corrections (7.13 à 7.16) doivent être **validées ensemble** pour s’assurer qu’elles fonctionnent en cohérence et sans régression.

---

### **📌 Fichiers à tester**


| **Fichier/Feature**                                | **Action requise**                                                                    | **Test à effectuer**                                                                           |
| -------------------------------------------------- | ------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| Tous les écrans (`fsdeploy/lib/ui/screens/`)       | Vérifier que `self.app.config` et `self.app.bridge` sont accessibles et fonctionnels. | Lancer `fsdeploy` et tester l’accès aux écrans (`ModuleRegistryScreen`, `CrossCompileScreen`). |
| `fsdeploy/__main__.py`                             | Confirmer que la configuration est bien passée à `FsDeployApp`.                       | Vérifier les logs pour s’assurer que `FsDeployConfig` est initialisé.                          |
| Scripts init (`fsdeploy.init`, `fsdeploy.service`) | Vérifier que les scripts s’exécutent sans erreur.                                     | Lancer `./fsdeploy/contrib/openrc/fsdeploy.init start` et `systemctl start fsdeploy.service`.  |
| `CONTRIBUTING.md`                                  | Vérifier que la documentation pour `contrib/` est claire et complète.                 | Relire la section ajoutée et valider son contenu.                                              |


---

### **📌 Instructions rapides**

1. **Lancer fsdeploy** :
  ```bash
   python -m fsdeploy --run
  ```
  - **Vérifier les logs** pour confirmer que :
    - `FsDeployConfig` est bien initialisé.
    - Les écrans (`ModuleRegistryScreen`, `CrossCompileScreen`) accèdent à `self.app.config` et `self.app.bridge`.
2. **Tester les scripts init** :
  ```bash
   ./fsdeploy/contrib/openrc/fsdeploy.init start
   systemctl start fsdeploy.service
  ```
  - **Vérifier qu’aucun message d’erreur** n’apparaît.
3. **Valider la documentation** :
  - Lire la nouvelle section dans `CONTRIBUTING.md` pour s’assurer qu’elle est claire.

---

---

**Prochaine étape** :  
**Teste l’intégration globale des corrections.**

**Besoin d’aide pour rédiger un script de test ou analyser les logs ?** 🚀
