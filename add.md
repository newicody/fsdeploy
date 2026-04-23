# add.md — 39.1 : Audit et Standardisation "Zéro-OS"

## 🛠️ 1. Audit des Screens (Scan de Pollution)
- Parcourir `lib/ui/screens/*.py` et lister les occurrences de :
    - `subprocess.run/Popen`, `os.system`, `shutil.copy/move`, `pathlib.Path.write_text`.
- **Action** : Créer un tableau de correspondance pour le `intents.ini`.

## 🛠️ 2. Standardisation du Data Flow (Consommation)
- Remplacer les scans de hardware dans les écrans par :
  `data = self.bridge.get_detected("disks")` ou `networks`.
- **Objectif** : Les écrans ne doivent plus "chercher", ils doivent "demander" au Bridge.

## 🛠️ 3. Refactoring Lot #1 : Écrans de Préparation (Action)
- **Cible** : `DiskScreen`, `PartitionScreen`, `FormatScreen`, `ZfsScreen`.
- **Structure** :
    - Supprimer toute commande système.
    - Émettre une intention : `self.bridge.execute(intent_id, params)`.
    - S'abonner au canal de log du Bridge pour afficher la progression.

## 🛠️ 4. Intégration du Status Widget
- Injecter un composant `LogTerm` (basé sur RichLog) dans chaque écran d'exécution.
- Le Bridge doit router le `stdout` du Scheduler directement vers ce composant.
- **Résultat** : L'utilisateur voit ZFS ou MKFS travailler en direct sans gel de l'interface.

## 🛠️ 5. Finalisation du Sudo Agent
- Brancher le déclenchement du `SudoModal` lors du signal `NEED_AUTH` du Scheduler.
- Garantir que le mot de passe est transmis au pipe `stdin` du processus de la Cage.
