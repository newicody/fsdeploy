# add.md — 38.2 : Pilotage du Scheduler par les champs Config

## 🛠 1. Analyse des Champs ConfigObj
- Le Scheduler doit scanner les fichiers de configuration du dépôt.
- **Identification des marqueurs** :
    - Repérer les clés indiquant un besoin de privilèges (ex: `need_root=1`, `sudo=true`).
    - Repérer les clés indiquant une action en milieu isolé (ex: `target=chroot`, `use_cage=true`).

## 🛠 2. Automatisation du Flux de Travail
Modifier `lib/scheduler.py` pour automatiser ce cycle :
1. **Réception** d'un ID de config depuis le Bridge.
2. **Lecture** du bloc correspondant dans le fichier de config.
3. **Challenge** : Si la config marque l'action comme protégée, émettre un signal `NEED_PASS` au Bridge.
4. **Exécution** : 
    - Si `chroot` est requis : Utiliser le bootstrap `/opt/fsdeploy/bootstrap`.
    - Si `sudo` est requis : Injecter le pass via `Popen` et `stdin`.
    - Appliquer les paramètres (flags, chemins) définis dans les champs de la config.

## 🛠 3. Sécurisation des Montages (Overlay/ZFS)
- Pour toute section de montage trouvée dans la config :
    - Le Scheduler doit vérifier si le point de montage existe dans la cage.
    - Exécuter le montage via le Runner Sudo.

## 🛠 4. Mise à jour du Bridge
- Le Bridge ne doit plus envoyer de "commandes", mais des "IDs de section" de ta config.
- Il doit être prêt à intercepter la demande de mot de passe du Scheduler pour afficher le `SudoModal`.
