# PLAN.md — fsdeploy

> **Urgence** : Restauration de la logique de déploiement Debian Live.

---

## 🚧 Tâche active — 27.1 (Restaurer & Fusionner)
1. **Extraction** : Demander au worker d'extraire la logique système de l'ancienne version de `launch.sh` (via git checkout/show).
2. **Réintégration** : Replacer la détection Debian Live et l'installation des dépendances APT dans le nouveau `launch.sh`.
3. **Audit Requirements** : Vérifier que `requirements.txt` correspond aux versions stables utilisées précédemment.
4. **Validation du lancement** : S'assurer que le script prépare le système AVANT de lancer l'UI.
