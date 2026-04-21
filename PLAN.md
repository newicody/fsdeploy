# PLAN.md — fsdeploy

> **Itération** : 120 | **Focus** : Étanchéité Hôte/Cible (Dracut)
> **Objectif** : Empêcher la pollution du système Live par les outils de génération de noyau.

---

## 🚧 Tâche active — 28.1 (Audit des appels Système)
- **Vérification** : S'assurer que TOUS les appels à `dracut` dans le code source sont préfixés par une commande de chroot ou exécutés via un namespace isolé.
- **launch.sh** : Retirer `dracut` de la liste des dépendances APT de l'hôte si le worker l'y a mis par erreur.
- **Validation** : Le script doit installer `live-boot` et `initramfs-tools` sur l'hôte, et RIEN D'AUTRE concernant le boot.