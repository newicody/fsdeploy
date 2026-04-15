# Contribution à fsdeploy

Ce document décrit comment contribuer au projet fsdeploy.

## Organisation des contributions

### Répertoire `fsdeploy/contrib/`

Ce répertoire contient des scripts et configurations pour l'intégration avec divers systèmes d'initialisation et outils externes.

- `openrc/` : Scripts pour OpenRC (init script).
- `systemd/` : Fichiers de service systemd.
- `test/` : Scripts et configurations pour tester les contributions (les scripts exécutables doivent avoir `chmod +x`).
- D'autres sous‑répertoires peuvent être ajoutés pour d'autres systèmes (sysvinit, runit, etc.)

#### Permissions attendues

- Les scripts OpenRC (`fsdeploy.init`) doivent être **exécutables** (`chmod +x`).
- Les fichiers systemd (`.service`) doivent avoir les permissions **644** (`chmod 644`).
- Les scripts de test situés dans `test/` qui sont destinés à être exécutés doivent également être rendus exécutables.

Ces permissions sont vérifiées automatiquement par le script `scripts/validate-integration.sh`.

### Ajout d'un nouveau système d'initialisation

1. Créez un sous‑répertoire sous `fsdeploy/contrib/` (ex: `mysys/`).
2. Placez‑y les fichiers nécessaires (script d'init, unité systemd, etc.).
3. Assurez‑vous que les permissions sont correctes.
4. Mettez à jour la documentation (ce fichier) pour décrire brièvement le nouveau système.

### Tests

Avant de soumettre une contribution, exécutez les scripts de validation :

```bash
bash scripts/validate-integration.sh
```

Cela vérifiera entre autres les permissions et l'accès au bridge.

### Convention de code

- Suivez le style de code existant (PEP 8 pour Python, shellcheck pour les scripts bash).
- Ajoutez des tests unitaires pour les nouvelles fonctionnalités.

Merci de contribuer !
