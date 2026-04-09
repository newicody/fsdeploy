# Manuel utilisateur de fsdeploy

## Vue d'ensemble

fsdeploy est un gestionnaire de déploiement et d'orchestration pour systèmes ZFS avec support de noyaux multiples, snapshots, streaming et interface utilisateur riche.

Il permet de :

- Détecter et importer automatiquement les pools ZFS.
- Provisionner et activer des noyaux (kernels) et des initramfs.
- Créer et restaurer des snapshots de configuration.
- Gérer des modules externes (extensions).
- Streamer l’interface graphique vers YouTube (mode initramfs).
- Afficher une interface textuelle (TUI) avec des écrans de contrôle temps‑réel.

## Installation

*(À compléter selon le mode de distribution.)*

## Premiers pas

1. **Lancer fsdeploy** : `python -m fsdeploy`
2. **Naviguer dans l’interface** : utiliser les touches fléchées et `Enter`.
3. **Importer un pool** : depuis l’écran principal, menu *Pool → Importer*.
4. **Configurer un kernel** : menu *Kernel → Lister / Provisionner*.

## Référence des commandes CLI

*(À compléter avec les options `--log-persist`, `--scan-squashfs`, etc.)*

## Configuration

Le fichier `fsdeploy.conf` (généralement dans `/etc/fsdeploy/`) contient tous les paramètres modifiables. Les sections principales sont décrites dans le fichier d’exemple.

## Dépannage

### Logs

Consultez les logs avec l’écran *Historique* de la TUI ou utilisez l’option `--log-persist` pour les sauvegarder.

### Vérification du scheduler

Si vous suspectez que certaines tâches ne sont pas exécutées correctement par le scheduler, vous pouvez lancer une vérification via l’intent `scheduler.verify` (disponible dans l’écran de débogage `x`). Cette vérification parcourt toutes les tâches définies dans le programme et vérifie leur intégration avec le système d’intents. Un rapport est généré et affiché dans les logs.

### Problèmes courants

- **Pool non détecté** : assurez-vous que le pool ZFS est importable (`zpool import`). L’intent `pool.import_all` peut forcer l’import.
- **Échec de montage** : vérifiez que le dataset n’est pas déjà monté ailleurs et que l’utilisateur a les droits nécessaires.
- **Kernel introuvable** : le dataset boot doit contenir des fichiers `vmlinuz-*` ou `initrd.img-*`. Vous pouvez également compiler un noyau via l’écran *Kernel*.

## Bridge UI‑Scheduler

Pour comprendre comment l'interface utilisateur communique avec le scheduler et respecte l'architecture event‑driven, consultez [bridge_ui_scheduler.md](bridge_ui_scheduler.md).

## Développement

Pour contribuer au projet, voir le dépôt Git et les consignes de contribution.

---

*(documentation à compléter)*
