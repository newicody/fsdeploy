# add.md — Améliorations proposées

**Date** : 2026-04-09

---

## 1. Écrans TUI : pattern uniforme de câblage

**Problème** : Chaque écran réinvente sa connexion au scheduler. Certains ne sont pas connectés du tout.

**Solution** : Créer un mixin `BridgeScreenMixin` dans `lib/ui/compat.py` :

```python
class BridgeScreenMixin:
    """Mixin pour tous les écrans qui émettent des intents."""

    def emit(self, event_name: str, **params) -> str:
        return self.app.bridge.emit(event_name, **params)

    def _refresh_from_store(self):
        """Appelé par le timer de refresh — poll les tickets."""
        self.app.bridge.poll()
```

Chaque écran hérite de ce mixin. Plus de code de bridge dupliqué.

---

## 2. Dry-run mode global

**Problème** : Aucun moyen de tester le flux complet sans toucher au système réel.

**Solution** : Ajouter `--dry-run` au CLI et à la config. Quand activé :
- `mount -t zfs` → log la commande, retourne succès fictif
- `zpool import` → idem
- `zfs snapshot` → idem
- Toutes les tâches reçoivent `dry_run=True` dans leur contexte

Fichiers : `lib/daemon.py`, `lib/function/*/` (toutes les tâches), `__main__.py`

---

## 3. Health-check au démarrage

**Problème** : Si ZFS n'est pas chargé, si le venv est cassé, si les permissions sont mauvaises — on découvre tardivement.

**Solution** : Intent `system.healthcheck` exécuté automatiquement au boot du daemon :
- Vérifie `modprobe zfs`
- Vérifie `zpool status` accessible
- Vérifie permissions sudoers
- Vérifie espace disque
- Résultat affiché sur WelcomeScreen

Fichiers : `lib/intents/system_intent.py` (ajouter `HealthCheckIntent`), `lib/ui/screens/welcome.py`

---

## 4. Notifications TUI unifiées

**Problème** : Les écrans utilisent `self.notify()` de manière inconsistante. Pas de notification pour les événements bus importants.

**Solution** : Le bridge écoute `task.failed` et `task.finished` sur le MessageBus global et appelle `app.notify()` automatiquement. Les écrans n'ont plus besoin de gérer les notifications manuellement pour les erreurs.

Fichier : `lib/ui/app.py`

---

## 5. Rollback automatique des montages

**Problème** : Si le processus crash pendant une séquence de montages, les montages restent.

**Solution** : `MountManager` dans `lib/function/mount/` qui :
- Enregistre chaque montage dans un journal (`/tmp/fsdeploy-mounts.json`)
- Au démarrage, vérifie si des montages orphelins existent
- Propose un cleanup automatique
- `umount -R /mnt` en shutdown hook

Fichiers : `lib/function/mount/manager.py` (nouveau), `lib/daemon.py` (hook shutdown)

---

## 6. Export/import de configuration de déploiement

**Problème** : Pas moyen de sauvegarder une config de déploiement complète et la réappliquer.

**Solution** : Les presets JSON existants sont étendus pour inclure :
- Mapping montages
- Noyau sélectionné + symlinks
- Type initramfs + paramètres
- Paramètres ZBM
- Paramètres stream

Intent `preset.export` / `preset.import` via PresetsScreen.

Fichiers : `lib/intents/system_intent.py`, `lib/ui/screens/presets.py`

---

## 7. Mode recovery

**Problème** : Si le boot ZBM échoue, pas d'outil de diagnostic intégré.

**Solution** : `python3 -m fsdeploy --recovery` qui :
- Liste tous les pools importables
- Tente l'import de chacun
- Vérifie la cohérence
- Propose des corrections (reimport, rollback snapshot, reconfiguration ZBM)

Fichier : `__main__.py` (nouvelle sous-commande), `lib/intents/system_intent.py`

---

## 8. Métriques de performance des tâches

**Problème** : Pas de visibilité sur les tâches lentes ou qui échouent souvent.

**Solution** : Le scheduler enregistre automatiquement durée + succès/échec de chaque tâche dans le HuffmanStore. MetricsScreen affiche :
- Top 10 tâches les plus lentes
- Taux d'échec par type de tâche
- Historique d'exécution

Déjà partiellement présent dans le code — à câbler dans MetricsScreen.

---

## Résumé des fichiers à créer

| Fichier | Description |
|---------|-------------|
| `lib/ui/mixins.py` | `BridgeScreenMixin` |
| `lib/function/mount/manager.py` | MountManager avec journal et cleanup |

## Résumé des fichiers à modifier

Voir la table dans PLAN.md section "Fichiers à modifier".
