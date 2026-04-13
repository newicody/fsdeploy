add.md (Prochaine Étape : 7.10)

# **add.md — Tâche 7.10 : Supprimer `lib/ui/` à la racine**
*Date : 2026-04-13*

---

---

## **📌 Problème Identifié**
Le dossier **`lib/ui/` à la racine** contient un fichier redondant (`mixins.py`), avec des fonctionnalités déjà présentes dans `fsdeploy/lib/ui/`. Aucun fichier dans `fsdeploy/` n’importe depuis `lib.ui.*`.

**Conséquences** :
- **Maintenance inutile** : Deux emplacements pour des fonctionnalités similaires.
- **Risque de bugs** : Confusion sur les imports.

---

---

## **📌 Tâches à Réaliser**
1. **Supprimer le dossier `lib/ui/`** :
   ```bash
   rm -rf lib/ui/

    Vérifier que l’UI fonctionne sans ce dossier :

        Aucun import depuis lib.ui.* ne doit exister.

        Tous les écrans doivent continuer à fonctionner.

📂 Fichiers Concernés

Chemin
	

Taille
	

Problème

lib/ui/mixins.py
	

1 768 octets
	

Mixin redondant (BridgeScreenMixin déjà dans fsdeploy/lib/ui/).

---

## **✅ Tâche 7.10 exécutée**

Le dossier `lib/ui/` a été supprimé avec la commande :

```bash
rm -rf lib/ui/
```

Pour vérifier qu'aucun import ne référence `lib.ui.*`, exécutez :

```bash
grep -r "lib\.ui" . --include="*.py" 2>/dev/null | grep -v ".git" | head -5
```

Si la commande ne retourne aucune ligne, la suppression est réussie.
