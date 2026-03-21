# Fichiers à intégrer dans fsdeploy

## Session du 21/03/2026 — Tasks manquantes

**Total : 27 fichiers, ~2930 lignes de code**

---

## Nouveaux fichiers (complets)

### 1. `lib/function/kernel/switch.py` — 315 lignes
Tasks kernel : switch, install, compile.

```
KernelSwitchTask   — bascule vmlinuz/initramfs via symlinks
KernelInstallTask  — installe depuis .deb ou fichiers directs
KernelCompileTask  — compile depuis sources avec config
```

### 2. `lib/function/network/setup.py` — 260 lignes
Tasks réseau : setup, status, wait.

```
NetworkSetupTask   — DHCP/static, timeout, connectivity check
NetworkStatusTask  — état de l'interface réseau
NetworkWaitTask    — attendre la connectivité
```

### 3. `lib/function/service/install.py` — 340 lignes
Tasks services système : install, uninstall, status.

```
ServiceInstallTask   — install service (systemd/openrc/sysvinit/upstart)
ServiceUninstallTask — désinstalle le service
ServiceStatusTask    — vérifie l'état du service
```

### 4. `lib/function/rootfs/switch.py` — 320 lignes
Tasks rootfs overlay complet.

```
RootfsMountTask   — monte squashfs + zfs upper
RootfsSwitchTask  — bascule vers nouveau rootfs à chaud
RootfsUpdateTask  — sync_upper, rebuild_sfs, clean_upper
RootfsUmountTask  — démonte le rootfs overlay
```

### 5. `lib/function/stream/youtube.py` — 320 lignes
Tasks streaming YouTube complet.

```
StreamStartTask   — lance ffmpeg vers YouTube RTMP
StreamStopTask    — arrête le stream
StreamStatusTask  — vérifie l'état du stream
StreamTestTask    — test de connectivité RTMP
StreamRestartTask — redémarre le stream
```

### 6. `lib/function/detect/role_patterns.py` — 350 lignes
Détection des rôles datasets : 15 rôles, magic bytes, scoring multi-signaux.

```
ROLE_PATTERNS (15 rôles) : boot, kernel, initramfs, modules, rootfs, 
                           squashfs, efi, python_env, overlay, config,
                           images, archive, snapshot, cache, log, data

detect_magic()              — détection par magic bytes
scan_directory()            — scan et génération de signaux
compute_aggregate_confidence() — scoring final
get_role_color/emoji/description() — helpers TUI
```

### 7. `lib/ui/screens/graph.py` — 340 lignes
GraphViewScreen : visualisation temps réel du scheduler.

```
PipelineStages  — affiche EventQueue → IntentQueue → TaskGraph → Done
TaskDetail      — détails de la tâche active
TaskHistory     — historique scrollable des tâches
GraphViewScreen — écran principal avec animation 10 FPS
```

### 8. `lib/intents/system_intent.py` — 185 lignes
Intents système complets.

```
Coherence : coherence.check
Snapshots : snapshot.list, snapshot.create, snapshot.rollback, snapshot.send
Stream    : stream.start, stream.stop, stream.status, stream.test, stream.restart
Network   : network.setup, network.status, network.wait
Rootfs    : rootfs.mount, rootfs.switch, rootfs.update, rootfs.umount
Service   : service.install, service.uninstall, service.status
```

---

## Fichiers `__init__.py` créés

| Chemin | Contenu |
|--------|---------|
| `lib/function/__init__.py` | Re-exports principaux |
| `lib/function/kernel/__init__.py` | KernelSwitch/Install/CompileTask |
| `lib/function/kernel/install.py` | Re-export |
| `lib/function/kernel/compile.py` | Re-export |
| `lib/function/network/__init__.py` | NetworkSetup/Status/WaitTask |
| `lib/function/service/__init__.py` | ServiceInstall/Uninstall/StatusTask |
| `lib/function/rootfs/__init__.py` | RootfsMount/Switch/Update/UmountTask |
| `lib/function/rootfs/mount.py` | Re-export |
| `lib/function/rootfs/update.py` | Re-export |
| `lib/function/stream/__init__.py` | StreamStart/Stop/Status/Test/RestartTask |
| `lib/function/detect/__init__.py` | EnvironmentDetectTask + role_patterns |
| `lib/function/boot/__init__.py` | BootInitTask, InitramfsBuildTask |
| `lib/function/pool/__init__.py` | PoolStatus/Import/Export/ScrubTask |
| `lib/function/dataset/__init__.py` | DatasetMount/Create/Destroy/ListTask |
| `lib/function/snapshot/__init__.py` | SnapshotCreate/Rollback/Send/ListTask |
| `lib/function/snapshot/rollback.py` | Re-export |
| `lib/function/coherence/__init__.py` | CoherenceCheckTask, Report, Result |
| `lib/function/live/__init__.py` | LiveSetupTask |
| `lib/ui/screens/__init__.py` | Import conditionnel de tous les écrans |

---

## Vérifications effectuées

- ✅ Syntaxe Python : tous les fichiers OK (`py_compile`)
- ✅ Imports cohérents avec l'architecture existante
- ✅ Decorateurs `@security.*` pour toutes les tasks
- ✅ `required_locks()` et `required_resources()` implémentés
- ✅ `executor = "threaded"` pour les tasks longues
- ✅ Fallback ASCII pour framebuffer (`IS_FB = os.environ.get("TERM") == "linux"`)

---

## Fichiers à supprimer (doublons/stubs)

```bash
rm -f lib/function/pool/import.py   # stub vide, la vraie implémentation est dans status.py
```

---

## Commandes d'intégration

```bash
# 1. Copier les fichiers dans le repo
cp -r /home/claude/fsdeploy/lib/* /path/to/fsdeploy/lib/

# 2. Supprimer les stubs
rm -f lib/function/pool/import.py

# 3. Vérifier la syntaxe
python3 -m py_compile lib/**/*.py

# 4. Commit
git add -A
git commit -m "feat: add missing tasks (kernel, network, service, rootfs, stream, detect, graph)"
```

---

## État final du projet

### Tasks par domaine

| Domaine | Tasks | État |
|---------|-------|------|
| detect/ | EnvironmentDetectTask, role_patterns | ✅ |
| live/ | LiveSetupTask | ✅ existant |
| boot/ | BootInitTask, InitramfsBuildTask | ✅ existant |
| kernel/ | KernelSwitch/Install/CompileTask | ✅ **NOUVEAU** |
| rootfs/ | RootfsMount/Switch/Update/UmountTask | ✅ **NOUVEAU** |
| dataset/ | DatasetMount/Create/Destroy/ListTask | ✅ existant |
| pool/ | PoolStatus/Import/Export/ScrubTask | ✅ existant |
| snapshot/ | SnapshotCreate/Rollback/Send/ListTask | ✅ existant |
| stream/ | StreamStart/Stop/Status/Test/RestartTask | ✅ **COMPLET** |
| network/ | NetworkSetup/Status/WaitTask | ✅ **NOUVEAU** |
| service/ | ServiceInstall/Uninstall/StatusTask | ✅ **NOUVEAU** |
| coherence/ | CoherenceCheckTask | ✅ existant |

### Intents couverts

| Event | Intent | Task |
|-------|--------|------|
| `kernel.switch` | KernelSwitchIntent | KernelSwitchTask |
| `kernel.install` | KernelInstallIntent | KernelInstallTask |
| `kernel.compile` | KernelCompileIntent | KernelCompileTask |
| `network.setup` | NetworkSetupIntent | NetworkSetupTask |
| `network.status` | NetworkStatusIntent | NetworkStatusTask |
| `network.wait` | NetworkWaitIntent | NetworkWaitTask |
| `rootfs.mount` | RootfsMountIntent | RootfsMountTask |
| `rootfs.switch` | RootfsSwitchIntent | RootfsSwitchTask |
| `rootfs.update` | RootfsUpdateIntent | RootfsUpdateTask |
| `rootfs.umount` | RootfsUmountIntent | RootfsUmountTask |
| `service.install` | ServiceInstallIntent | ServiceInstallTask |
| `service.uninstall` | ServiceUninstallIntent | ServiceUninstallTask |
| `service.status` | ServiceStatusIntent | ServiceStatusTask |
| `stream.start` | StreamStartIntent | StreamStartTask |
| `stream.stop` | StreamStopIntent | StreamStopTask |
| `stream.status` | StreamStatusIntent | StreamStatusTask |
| `stream.test` | StreamTestIntent | StreamTestTask |
| `stream.restart` | StreamRestartIntent | StreamRestartTask |
| `coherence.check` | CoherenceCheckIntent | CoherenceCheckTask |
| `snapshot.*` | Snapshot*Intent | Snapshot*Task |

### Écrans TUI

12 écrans disponibles avec navigation :
`h` welcome, `d` detection, `m` mounts, `k` kernel, `i` initramfs,
`p` presets, `c` coherence, `s` snapshots, `y` stream, `o` config,
`x` debug, `g` **graph** (nouveau)

---

## Résumé

**Avant** : 46 modules Python, tasks manquantes pour kernel/network/service/rootfs complet

**Après** : ~73 modules Python, architecture complète avec :
- Toutes les tasks référencées dans les intents
- Tous les intents pour system_intent.py
- GraphViewScreen pour visualisation scheduler
- 15 rôles de détection avec scoring multi-signaux
