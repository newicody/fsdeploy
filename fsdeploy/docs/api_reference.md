# Référence des intents et endpoints

Cette documente liste les intents (événements) disponibles dans fsdeploy, leur but, leurs paramètres, et les tâches qu'ils génèrent.

## Introduction

Les intents sont enregistrés via le décorateur `@register_intent(event_name)`. Ils sont déclenchés par des événements (TUI, CLI, timers, etc.) et produisent une ou plusieurs tâches exécutées par le scheduler.

Chaque intent appartient à un domaine (detection, kernel, module, config, snapshot, etc.).

## Liste des intents

### Détection et pools

| Intent | Description | Paramètres | Tâche(s) |
|--------|-------------|------------|----------|
| `detection.start` | Détection complète (pools + datasets + partitions) | `force` (bool) | `PoolImportAllTask`, `DatasetListTask`, `PartitionDetectTask`, `DatasetProbeTask` |
| `detection.probe_datasets` | Analyse de datasets spécifiques | `datasets` (list) | `DatasetProbeTask` pour chaque dataset |
| `pool.import_all` | Importe tous les pools ZFS disponibles | (aucun) | `PoolImportAllTask` |
| `mount.verify` | Vérifie l'état de montage d'un dataset | `dataset`, `mountpoint` | `MountVerifyTask` |
| `mount.umount` | Démonte un dataset | `dataset`, `mountpoint` | `UmountDatasetTask` |

### Kernel et initramfs

| Intent | Description | Paramètres | Tâche(s) |
|--------|-------------|------------|----------|
| `kernel.list` | Liste les kernels disponibles | `pool` (optionnel) | `KernelListTask` |
| `kernel.provision` | Provisionne un kernel (copie/lien) | `kernel_path`, `target_pool`, `method` | `KernelProvisionTask` |
| `kernel.switch` | Active un kernel pour le prochain boot | `kernel_version` | `KernelSwitchTask` |
| `kernel.install` | Installe un kernel depuis un paquet Debian | `version` | `KernelInstallTask` |
| `kernel.compile` | Compile un kernel depuis les sources | `config_url`, `threads` | `KernelCompileTask` |
| `initramfs.build` | Construit un initramfs | `type`, `kernel_version` | `InitramfsBuildTask` |
| `initramfs.list` | Liste les initramfs disponibles | (aucun) | `InitramfsListTask` |

### Modules

| Intent | Description | Paramètres | Tâche(s) |
|--------|-------------|------------|----------|
| `module.list` | Liste les modules distants et installés | `filter` | `ModuleListTask` |
| `module.install` | Installe un module depuis le registre | `name`, `version` | `ModuleInstallTask` |
| `module.uninstall` | Désinstalle un module | `name` | `ModuleUninstallTask` |
| `module.update` | Met à jour tous les modules installés | `force` | `ModuleUpdateTask` |

### Snapshots

| Intent | Description | Paramètres | Tâche(s) |
|--------|-------------|------------|----------|
| `snapshot.list` | Liste les snapshots d'un dataset | `dataset` | `SnapshotListTask` |
| `snapshot.create` | Crée un snapshot | `dataset`, `name` | `SnapshotCreateTask` |
| `snapshot.rollback` | Restaure un snapshot | `dataset`, `name` | `SnapshotRollbackTask` |

### Configuration

| Intent | Description | Paramètres | Tâche(s) |
|--------|-------------|------------|----------|
| `config.snapshot.save` | Sauvegarde la configuration actuelle | `snapshot_name`, `config_path` | `ConfigSnapshotTask` |
| `config.snapshot.restore` | Restaure une configuration | `snapshot_name` | `ConfigRestoreTask` |
| `config.snapshot.list` | Liste les snapshots de configuration | (aucun) | `ConfigSnapshotListTask` |
| `config.reload` | Recharge la configuration depuis le disque | (aucun) | `ConfigReloadTask` (à implémenter) |

### ZFSBootMenu

| Intent | Description | Paramètres | Tâche(s) |
|--------|-------------|------------|----------|
| `zbm.install` | Installe ZFSBootMenu dans l'EFI | `efi_device`, `efi_mount` | `ZBMInstallTask` |
| `zbm.status` | Vérifie l'état de ZFSBootMenu | (aucun) | `ZBMStatusTask` |
| `zbm.validate` | Valide la configuration ZBM | (aucun) | `ZBMPreflightTask` |

### Stream YouTube

| Intent | Description | Paramètres | Tâche(s) |
|--------|-------------|------------|----------|
| `stream.start` | Démarre un stream YouTube | `youtube_key`, `resolution`, `fps` | `StreamStartTask` |
| `stream.stop` | Arrête le stream | (aucun) | `StreamStopTask` |
| `stream.status` | Récupère l'état du stream | (aucun) | `StreamStatusTask` |

### Scheduler et débogage

| Intent | Description | Paramètres | Tâche(s) |
|--------|-------------|------------|----------|
| `scheduler.verify` | Vérifie l'intégration des tâches avec le scheduler | (aucun) | `SchedulerVerifyTask` |
| `debug.exec` | Exécute une commande arbitraire (debug) | `cmd`, `sudo` | `DebugExecTask` |
| `security.status` | Récupère l'état de la configuration de sécurité | `config_path` | `SecurityStatusTask` |

### Presets de boot

| Intent | Description | Paramètres | Tâche(s) |
|--------|-------------|------------|----------|
| `preset.list` | Liste les presets | (aucun) | `PresetListTask` |
| `preset.save` | Sauvegarde un preset | `name`, `data` | `PresetSaveTask` |
| `preset.activate` | Active un preset | `name` | `PresetActivateTask` |
| `preset.delete` | Supprime un preset | `name` | `PresetDeleteTask` |

## Utilisation via TUI

Dans l'interface TUI, les intents sont déclenchés via :

- Les écrans dédiés (ex: écran Kernel → `kernel.list` puis `kernel.switch`)
- Le menu Debug (touche `x`) permet d'émettre des intents manuellement
- Les actions automatiques (timer, udev, etc.)

## Utilisation via CLI

Les intents peuvent être émis via l'option `--trigger` (à implémenter) ou en utilisant le socket IPC.

Exemple (hypothétique) :

```bash
python3 -m fsdeploy --trigger "detection.start" --params '{"force": true}'
```

## Format des réponses

Les tâches produites retournent un objet `CommandResult` avec les champs :

- `success` : booléen indiquant si l'exécution s'est bien passée
- `stdout` : sortie standard de la commande
- `stderr` : sortie d'erreur
- `returncode` : code de retour
- `duration` : durée d'exécution en secondes

Les résultats sont stockés dans le `RuntimeState` et accessibles via l'écran Debug (touche `x`).

## Ajout d'un nouvel intent

Pour ajouter un nouvel intent :

1. Créer une sous‑classe de `Intent` dans le fichier approprié sous `lib/intents/`.
2. Implémenter la méthode `build_tasks()` qui retourne une liste de tâches.
3. Décorer la classe avec `@register_intent("mon.event")`.
4. Éventuellement, ajouter une règle de sécurité via `@security.xxx.yyy`.

Exemple :

```python
@register_intent("mon.event")
class MonIntent(Intent):
    def build_tasks(self):
        return [MonTask(id="mon_task", params=self.params, context=self.context)]
```

## Référence API

Pour une liste détaillée des intents et endpoints, consultez [api_reference.md](api_reference.md).

---

*Documentation générée le 2026‑04‑07 – fsdeploy version 0.1.0 (alpha)*
