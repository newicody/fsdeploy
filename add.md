# add.md — 28.1 : Isolation Dracut

## 🛠 ACTION : Nettoyage de l'Hôte
1. Dans `launch.sh`, vérifie la fonction `install_dependencies`.
2. **INTERDICTION** d'installer `dracut` sur l'hôte. Si présent, le supprimer de la liste.
3. Assure-toi que seuls `live-boot` et `initramfs-tools` sont installés pour garantir le mode Live.

## 🛠 ACTION : Audit du Code de Déploiement
1. Analyse les fichiers de logique (ex: `lib/deploy/kernel.py` ou similaire).
2. Si `dracut` est appelé, il doit l'être via :
   `command = ["chroot", target_path, "dracut", ...]`
3. Si le code essaie d'installer `dracut` via le bridge/scheduler, l'ordre doit être envoyé vers l'environnement cible, jamais vers l'hôte.
