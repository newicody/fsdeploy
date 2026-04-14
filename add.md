# **add.md — Étape 7.10 : Supprimer `lib/ui/` à la racine**

*Date : 2026-04-13*

---

---

## **📌 Problème Identifié**

Le dossier `**lib/ui/` à la racine** contient un fichier redondant (`mixins.py`), avec des fonctionnalités déjà présentes dans `fsdeploy/lib/ui/`. Aucun fichier dans `fsdeploy/` n’importe depuis `lib.ui.*`.

**Conséquences** :

- **Maintenance inutile** : Deux emplacements pour des fonctionnalités similaires.
- **Risque de bugs** : Confusion sur les imports.

---

---

## **📌 Tâches à Réaliser**

1. **Supprimer le dossier `lib/ui/**` :
  ```bash
   rm -rf lib/ui/
  ```
2. **Vérifier que l’UI fonctionne sans ce dossier** :
  - Aucun import depuis `lib.ui.*` ne doit exister.
  - Tous les écrans doivent continuer à fonctionner normalement.

---

---

## **📂 Fichiers Concernés**


| **Chemin**         | **Taille**   | **Problème**                                                        |
| ------------------ | ------------ | ------------------------------------------------------------------- |
| `lib/ui/mixins.py` | 1 768 octets | Mixin redondant (`BridgeScreenMixin` déjà dans `fsdeploy/lib/ui/`). |


---

---

## **🔍 Validation Après Correction**

1. **Vérifier les imports** :
  ```bash
   grep -r "lib.ui" .
  ```
   → **Doit retourner 0 résultat** (aucun import depuis `lib.ui.*`).
2. **Exécuter l’application** :
  ```bash
   python -m fsdeploy
  ```
   → Doit lancer l’UI **sans erreur**.
3. **Vérifier que tous les écrans fonctionnent** :
  - Tester un écran (ex: `CrossCompileScreen`).
  - Tester le `ModuleRegistryScreen`.
  - Aucun message d’erreur lié à `BridgeScreenMixin` ne doit apparaître.
