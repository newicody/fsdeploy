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
   - Déplacer le service systemd (`fsdeploy.service`) dans `fs
