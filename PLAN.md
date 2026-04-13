PLAN.md — fsdeploy (Branche dev)

Dernière mise à jour : 2026-04-13
Objectif : Résoudre tous les problèmes de structure, de duplication, de configuration et d’initialisation identifiés.
✅ Tâches Terminées (7.0–7.9)

Étape
	

Description
	

Statut
	

Preuve

7.0
	

launch.sh : Branche dev par défaut + options --run/--no-run ajoutées.
	

✅
	

Fichier modifié et testé.

7.1
	

live/setup.py : Correction de l’initialisation des linux-headers via uname -r.
	

✅
	

Fichier modifié et testé.

7.2
	

Sync des écrans dans tests/ (stale copies) → Fichiers corrigés.
	

✅
	

Fichiers mis à jour.

7.4
	

README.md : Mise à jour des instructions d’installation pour dev.
	

✅
	

Fichier modifié et validé.

7.5
	

DIAGRAMS.md : Correction des chemins linux-headers.
	

✅
	

Fichier modifié.

7.6
	

fsdeploy_main_status.md : Suppression (obsolète).
	

✅
	

Fichier supprimé.

7.7
	

fsdeploy/lib/function/module/registry.py : Re-export corrigé.
	

✅
	

Fichier mis à jour.

7.8
	

Supprimer tests/fsdeploy/ (29 fichiers dupliqués).
	

✅
	

Dossier supprimé.

7.9
	

Nettoyer et centraliser contrib/ dans fsdeploy/contrib/ (suppression des doublons sysvinit/upstart).
	

✅
	

Dossier contrib/ nettoyé, fichiers OpenRC/systemd centralisés.
🔴 Tâches Restantes (Priorité Absolue)

Étape
	

Problème
	

Tâche à Réaliser
	

Fichiers Concernés
	

Statut

7.10
	

Redondance de lib/ui/ à la racine.
	

**Supprimer le dossier lib/ui/** (fichier mixins.py redondant).
	

lib/ui/mixins.py
	

⏳ À faire

7.11
	

Scheduler n’a pas de global_instance().
	

**Ajouter global_instance()** à fsdeploy/lib/scheduler/core/scheduler.py.
	

fsdeploy/lib/scheduler/core/scheduler.py
	

⏳

7.12
	

__main__.py ne passe pas runtime à FsDeployApp.
	

**Initialiser Runtime et FsDeployConfig** dans __main__.py et les passer à FsDeployApp.
	

fsdeploy/__main__.py
	

⏳

7.13
	

La config (FsDeployConfig) n’est pas utilisée dans les écrans.
	

**Passer self.app.config** aux écrans (ex: ModuleRegistryScreen).
	

fsdeploy/lib/ui/screens/module_registry.py
	

⏳

7.14
	

Le bridge ne fonctionne dans aucun écran.
	

Valider que self.app.bridge est fonctionnel dans tous les écrans.
	

Tous les écrans (ex: CrossCompileScreen)
	

⏳

7.15
	

Documentation absente pour contrib/.
	

**Ajouter une section dans CONTRIBUTING.md** expliquant où placer les scripts d’init.
	

CONTRIBUTING.md ou README.md
	

⏳

7.16
	

Permissions incorrectes sur les scripts init.
	

Vérifier et corriger les permissions (chmod +x pour OpenRC, chmod 644 pour systemd).
	

fsdeploy/contrib/openrc/fsdeploy.init, fsdeploy/contrib/systemd/fsdeploy.service
	

⏳
📌 Prochaine Tâche Prioritaire (7.10)
Problème

Le dossier **lib/ui/ à la racine** contient un fichier redondant (mixins.py), avec des fonctionnalités déjà présentes dans fsdeploy/lib/ui/. Aucun fichier dans fsdeploy/ n’importe depuis lib.ui.*.
Tâches à Réaliser

    Supprimer le dossier lib/ui/ à la racine :

     rm -rf lib/ui/

    Vérifier que l’UI fonctionne sans ce dossier :

        Aucun import depuis lib.ui.* ne doit exister dans le code.

        Tous les écrans doivent continuer à fonctionner normalement.

Fichiers Concernés

Chemin
	

Taille
	

Problème

lib/ui/mixins.py
	

1 768 octets
	

Mixin redondant (BridgeScreenMixin déjà dans fsdeploy/lib/ui/).
Validation Après Correction

    Vérifier les imports :

    grep -r "lib.ui" .  # Doit retourner 0 résultat

    Exécuter l’application :

    python -m fsdeploy

    → Doit lancer l’UI **sans erreur**.

📋 Checklist Globale Finale

    7.0 à 7.9 : Toutes terminées.

    7.10 : Supprimer lib/ui/ → Prochaine étape.

    7.11 : Ajouter global_instance() à Scheduler.

    7.12 : Initialiser Runtime et FsDeployConfig dans __main__.py.

    7.13 : Utiliser self.app.config dans les écrans.

    7.14 : Valider que le bridge fonctionne.

    7.15 : Mettre à jour la documentation (CONTRIBUTING.md).

    7.16 : Vérifier/corriger les permissions des scripts.
