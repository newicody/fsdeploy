# **add.md — Étape 7.11 : Ajouter `global_instance()` à `Scheduler**`

*Date : 2026-04-13*

---

---

## **📌 Problème Identifié**

Le `Scheduler` n’a **pas de méthode `global_instance()**`, donc le `SchedulerBridge` ne peut pas accéder au `Scheduler` global. Résultat :

- **Tous les écrans ont `self.app.bridge = None**`.
- Erreur **"bridge non disponible"** dans la console et l’UI.

---

---

## **📌 Tâches à Réaliser**

1. **Ajouter `global_instance()` à la classe `Scheduler**` dans `fsdeploy/lib/scheduler/core/scheduler.py` :
  ```python
   # Dans fsdeploy/lib/scheduler/core/scheduler.py, après la classe Scheduler :
   class Scheduler:
       _global_instance = None  # Ajouter cette ligne

       @classmethod
       def global_instance(cls):
           if cls._global_instance is None:
               from fsdeploy.lib.scheduler.core.resolver import Resolver
               from fsdeploy.lib.scheduler.core.executor import Executor
               from fsdeploy.lib.scheduler.runtime import Runtime
               cls._global_instance = cls(Resolver(), Executor(), Runtime())
           return cls._global_instance
  ```
2. **Vérifier que `Scheduler.global_instance()` retourne une instance** :
  ```bash
   python -c "from fsdeploy.lib.scheduler.core.scheduler import Scheduler; print(Scheduler.global_instance())"
  ```
   → Doit retourner une instance de `Scheduler` (pas `None`).

---

---

## **📂 Fichiers Concernés**


| **Chemin**                                 | **Type**           | **Modification Requise**                           |
| ------------------------------------------ | ------------------ | -------------------------------------------------- |
| `fsdeploy/lib/scheduler/core/scheduler.py` | Classe `Scheduler` | Ajouter `_global_instance` et `global_instance()`. |


---

---

## **🔍 Validation Après Correction**

1. **Vérifier l’instance globale** :
  ```bash
   python -c "from fsdeploy.lib.scheduler.core.scheduler import Scheduler; print(Scheduler.global_instance())"
  ```
   → Résultat attendu : `<fsdeploy.lib.scheduler.core.scheduler.Scheduler object at ...>`
2. **Vérifier que le `bridge` fonctionne** :
  - Lancer l’application :
  - Ouvrir un écran (ex: `CrossCompileScreen`).
  - Aucun message **"bridge non disponible"** ne doit apparaître.
3. **Vérifier que `SchedulerBridge` fonctionne** :
  - Dans un écran, tester :  
   → Doit fonctionner sans erreur.
