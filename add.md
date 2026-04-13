# **add.md — Tâche 7.9 : Nettoyer et Centraliser `contrib/`**
*Date : 2026-04-13*

---

---

## **📌 Problème Identifié**
La structure des dossiers **`contrib/`** et **`fsdeploy/contrib/`** est **désorganisée** :
- **`contrib/` à la racine** contient des scripts **sysvinit/upstart** obsolètes (peu utilisés aujourd’hui).
- **`fsdeploy/contrib/`** contient des scripts **OpenRC/systemd** modernes.
- **Redondance** : Les fichiers dans `contrib/sysvinit/fsdeploy` et `contrib/upstart/fsdeploy.conf` font doublon avec ceux dans `fsdeploy/contrib/openrc/` et `fsdeploy/contrib/systemd/`.

**Conséquences** :
- **Maintenance complexe** : Deux emplacements pour les scripts d’init.
- **Confusion** : Où placer les nouveaux scripts d’init ?
- **Incohérences** : Certains systèmes d’init (sysvinit/upstart) sont obsolètes.

---
---
## **📌 Tâches à Réaliser**
1. **Centraliser les fichiers utiles** dans `fsdeploy/contrib/` :
   - Déplacer les scripts de test (`test_*.sh`) de `contrib/integration/` vers `fsdeploy/contrib/integration/`.
   - Déplacer les scripts OpenRC (`fsdeploy.init`, `fsdeploy.initd`) dans `fsdeploy/contrib/openrc/`.
   - Déplacer le service systemd (`fsdeploy.service`) dans `fsdeploy/contrib/systemd/`.
2. **Supprimer les fichiers redondants** :
   - Supprimer `contrib/sysvinit/fsdeploy` (sysvinit obsolète).
   - Supprimer `contrib/upstart/fsdeploy.conf` (upstart obsolète).
3. **Supprimer le dossier `contrib/` à la racine** pour éviter toute confusion future.
4. **Vérifier que les scripts OpenRC/systemd fonctionnent** après le déplacement.

---
---
## **📂 Fichiers Concernés**
   **Chemin Actuel** | **Destination** | **Type** | **Problème** |
 |-------------------|-----------------|----------|--------------|
 | `contrib/integration/test_*.sh` | `fsdeploy/contrib/integration/` | Scripts de test | À centraliser. |
 | `contrib/sysvinit/fsdeploy` | **Supprimer** | Script sysvinit | Obsolète (remplacé par OpenRC). |
 | `contrib/upstart/fsdeploy.conf` | **Supprimer** | Fichier upstart | Obsolète (remplacé par systemd). |
 | `fsdeploy/contrib/openrc/fsdeploy.init` | `fsdeploy/contrib/openrc/` | Script OpenRC | **Correct** (à garder). |
 | `fsdeploy/contrib/openrc/fsdeploy.initd` | `fsdeploy/contrib/openrc/` | Script OpenRC | **Correct** (à garder). |
 | `fsdeploy/contrib/systemd/fsdeploy.service` | `fsdeploy/contrib/systemd/` | Service systemd | **Correct** (à garder). |

---
---
## **🔍 Validation Après Correction**
1. **Vérifier la nouvelle structure** :
   - `fsdeploy/contrib/integration/` doit contenir les scripts de test.
   - `fsdeploy/contrib/openrc/` doit contenir `fsdeploy.init` et `fsdeploy.initd`.
   - `fsdeploy/contrib/systemd/` doit contenir `fsdeploy.service`.
   - Plus de dossier `contrib/` à la racine.

2. **Vérifier que les scripts init fonctionnent** :
   - Tester le script OpenRC :
     ```bash
     sh fsdeploy/contrib/openrc/fsdeploy.init --help
     ```
   - Tester le service systemd (si systemd est installé) :
     ```bash
     systemctl status fsdeploy.service
     ```

3. **Exécuter les tests** (si applicable) :
   ```bash
   python -m pytest tests/ -v
