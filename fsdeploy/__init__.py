"""
fsdeploy
========
Système de déploiement ZFS/ZFSBootMenu depuis Debian Live.

Point d'entrée : python3 -m fsdeploy
Config partagée : fsdeploy.config.FsDeployConfig

Architecture par fichiers (un fichier = une responsabilité) :

    config.py               ← FsDeployConfig   (FONDATION — importée partout)
    │
    ├── core/
    │   ├── runner.py       ← CommandRunner     (subprocess + log temps réel)
    │   ├── detection/
    │   │   ├── pool.py     ← PoolDetector      (import/liste zpool)
    │   │   ├── dataset.py  ← DatasetDetector   (analyse et classification)
    │   │   ├── partition.py← PartitionDetector (EFI, boot, disques)
    │   │   └── report.py   ← DetectionReport   (synthèse + JSON)
    │   ├── zfs/
    │   │   ├── mount.py    ← MountManager      (mount/umount datasets)
    │   │   ├── snapshot.py ← SnapshotManager   (create/restore/list)
    │   │   └── dataset.py  ← DatasetManager    (create/set properties)
    │   ├── boot/
    │   │   ├── kernel.py   ← KernelManager     (find/copy/symlink noyaux)
    │   │   ├── initramfs.py← InitramfsBuilder  (dracut / cpio custom)
    │   │   ├── zbm.py      ← ZBMManager        (install/config ZFSBootMenu)
    │   │   └── preset.py   ← PresetManager     (CRUD presets dans config)
    │   ├── images/
    │   │   ├── squash.py   ← SquashManager     (mksquashfs rootfs/modules/python)
    │   │   └── overlay.py  ← OverlayManager    (montage lower+upper+merged)
    │   └── stream.py       ← StreamManager     (ffmpeg → YouTube)
    │
    └── ui/
        ├── app.py          ← FsDeployApp       (Textual App principale)
        ├── screens/
        │   ├── welcome.py  ← WelcomeScreen
        │   ├── detection.py← DetectionScreen
        │   ├── mounts.py   ← MountsScreen
        │   ├── kernel.py   ← KernelScreen
        │   ├── initramfs.py← InitramfsScreen
        │   ├── presets.py  ← PresetsScreen
        │   ├── coherence.py← CoherenceScreen
        │   ├── stream.py   ← StreamScreen
        │   └── snapshots.py← SnapshotsScreen
        └── widgets/
            ├── command_log.py ← CommandLog     (widget log commandes en live)
            ├── confirm.py     ← ConfirmDialog  (modale oui/non/annuler)
            └── status_bar.py  ← StatusBar
"""

__version__ = "0.1.0"

from fsdeploy.config import FsDeployConfig

__all__ = ["FsDeployConfig", "__version__"]
