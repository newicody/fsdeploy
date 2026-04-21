# PLAN.md — fsdeploy

> **Itération** : 117 | **Tâche** : Débianisation du Bootloader
> **Objectif** : Remplacer les résidus d'Ubuntu (Casper) par les standards Debian Live.

---

## 🚧 Tâche active — 27.2 (Migration Casper -> Live-Boot)
1. **Audit de launch.sh** : Identifier toutes les occurrences de "casper".
2. **Remplacement** : Utiliser `/lib/live/mount/medium` et `boot=live` pour la détection.
3. **Vérification** : S'assurer que les fonctions d'installation APT s'activent bien si l'un de ces marqueurs est trouvé.