# fsdeploy lib/ — Fichiers produits

## Vérification

- ✅ 68 fichiers Python (46 non-vides + 22 `__init__.py`)
- ✅ 45/45 imports runtime OK
- ✅ 3/3 tests d'intégration OK
- ✅ ~4870 lignes de code utile

## Fichiers à supprimer du repo

```
lib/ARCHITECTURE.py              ← remplacé par roadmap.md
lib/scheduler/intentlog/huffman.py  ← stub vide, supprimé
lib/scheduler/core/intent.py     ← doublon résolu dans model/intent.py
```

## Arborescence complète

```
lib/
├── daemon.py                              # Processus racine (scheduler + bus + TUI)
├── test_run.py                            # Tests d'intégration
│
├── bus/
│   └── __init__.py                        # TimerSource, InotifySource, UdevSource, SocketSource
│
├── scheduler/
│   ├── model/
│   │   ├── event.py                       # Event + Boot/Udev/Inotify/Timer/Signal/CLI
│   │   ├── task.py                        # Task base + run_cmd() + locks + lifecycle
│   │   ├── intent.py                      # Intent + IntentID hiérarchique
│   │   ├── resource.py                    # Resource hiérarchique + conflits
│   │   ├── lock.py                        # Lock exclusif/partagé
│   │   └── runtime.py                     # RuntimeState (lifecycle + locks + waiting)
│   ├── core/
│   │   ├── scheduler.py                   # Boucle event→intent→task→execute
│   │   ├── executor.py                    # Exécution sync/threaded
│   │   ├── resolver.py                    # Pipeline security→resources→locks
│   │   ├── runtime.py                     # Runtime (agrège state + queues)
│   │   └── registry.py                    # Registres task/executor/intent
│   ├── security/
│   │   ├── decorator.py                   # DSL @security.dataset.snapshot
│   │   └── resolver.py                    # Vérifie droits, produit locks
│   ├── queue/
│   │   ├── event_queue.py                 # PriorityQueue thread-safe
│   │   └── intent_queue.py                # FIFO + handlers event→intent
│   ├── graph/
│   │   ├── task_graph.py                  # DAG dépendances + cycle detection
│   │   └── resource_graph.py              # Graphe ownership + conflits
│   ├── intentlog/
│   │   └── log.py                         # Journal JSONL (audit + replay)
│   └── runtime/
│       ├── monitor.py                     # Métriques + observers
│       └── state.py                       # Re-export compat
│
├── function/
│   ├── test_task.py                       # TestTask validation
│   ├── detect/
│   │   └── environment.py                 # EnvironmentDetectTask (live/booted/initramfs)
│   ├── live/
│   │   └── setup.py                       # LiveSetupTask (APT, DKMS, groups, venv)
│   ├── boot/
│   │   ├── init.py                        # BootInitTask (génère /init zbm/minimal/stream)
│   │   └── initramfs.py                   # InitramfsBuildTask (dracut ou cpio)
│   ├── network/
│   │   └── setup.py                       # NetworkSetupTask (DHCP, connectivity)
│   ├── kernel/
│   │   ├── switch.py                      # KernelSwitch/Install/CompileTask
│   │   ├── install.py                     # Re-export
│   │   └── compile.py                     # Re-export
│   ├── rootfs/
│   │   ├── switch.py                      # RootfsSwitch/Mount/UpdateTask
│   │   ├── mount.py                       # Re-export
│   │   └── update.py                      # Re-export
│   ├── dataset/
│   │   ├── mount.py                       # DatasetMount/Create/Destroy/ListTask
│   │   └── destroy.py                     # Re-export
│   ├── pool/
│   │   ├── status.py                      # PoolStatus/Import/Export/ScrubTask
│   │   └── export.py                      # Re-export
│   ├── snapshot/
│   │   ├── create.py                      # SnapshotCreate/Rollback/Send/ListTask
│   │   └── rollback.py                    # Re-export
│   ├── stream/
│   │   └── youtube.py                     # StreamStart/Stop/StatusTask
│   ├── coherence/
│   │   └── check.py                       # CoherenceCheckTask (vérifie tout avant boot)
│   └── service/
│       └── install.py                     # ServiceInstallTask (systemd/openrc/sysvinit)
│
└── intents/
    ├── boot_intent.py                     # Boot/Snapshot/Stream/Coherence/Scrub intents
    └── test_intent.py                     # TestIntent
```
