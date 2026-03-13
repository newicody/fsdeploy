# Inventaire des fichiers -- ZFSBootMenu Custom

**22 fichiers — 10 822 lignes au total**

---

## Deploiement -- deploy/

| Fichier | Lignes | Role |
|---|---:|---|
| `deploy/deploy.sh` | 190 | Orchestrateur principal. Menu numerique (0 quitter, 1-8 etapes, 9 tout deployer, 10-13 utilitaires). Source config.sh, appelle les scripts lib/ via run_step. |
| `deploy/config.sh` | 126 | Source de verite. Pure ASCII. Definit SYSTEMS, KERNEL_LABEL, KERNEL_VER, INIT_TYPE, ROOTFS_LABEL, materiel, stream, reseau. Genere par detect.sh, editable manuellement. |

---

## Bibliotheque -- deploy/lib/

| Fichier | Lignes | Role |
|---|---:|---|
| `naming.sh` | 494 | Convention de nommage des images + `zbm_select_kernel()`. Fonctions zbm_path, zbm_dir, zbm_parse, zbm_list_sets, zbm_write_meta, zbm_read_meta. `zbm_select_kernel [--allow-new] [--label <l>] [--quiet]` : scanne boot_pool/images/kernels/, affiche un menu numerote avec kver/taille/modules, permet de choisir un existant ou d'en installer un nouveau. Retourne "<path>|<label>|<date>|<kver>" ou "new\|\|". |
| `detect.sh` | 467 | Detection materielle et ecriture de config.sh. EFI : liste toutes les partitions vfat+EFI/, menu de choix. Datasets : dynamiques depuis SYSTEMS. Lit KERNEL_VER depuis les .meta de boot_pool. Pure ASCII. |
| `datasets-check.sh` | 376 | Verification et creation des datasets ZFS. warn() presente. Modes : check, initial, full, --system. |
| `kernel.sh` | 269 | Installation kernel + modules dans boot_pool. Appelle `zbm_select_kernel --allow-new` pour afficher la liste des kernels existants et proposer d'en installer un nouveau. Ecrit KERNEL_VER + KERNEL_LABEL dans config.sh apres installation. |
| `rootfs.sh` | 201 | Installation du rootfs squashfs dans boot_pool. |
| `python-sfs.sh` | 127 | Construction de python-ver-date.sfs. |
| `initramfs.sh` | 362 | Construction de l'initramfs sans dracut. Pour le type minimal, appelle `zbm_select_kernel --quiet` pour obtenir la kver du kernel installe dans boot_pool (jamais uname -r). Zero dependance a la version du kernel pour les types zbm/zbm-stream. |
| `zbm.sh` | 128 | Installation de ZFSBootMenu dans boot_pool/efi/EFI/ZBM/. |
| `presets.sh` | 384 | Generation des presets de boot JSON. |
| `failsafe.sh` | 52 | Wrapper etape 8. |
| `coherence.sh` | 435 | Audit de coherence. |
| `import-mount.sh` | 402 | Import des pools et montage. |
| `umount.sh` | 71 | Demontage propre. |

---

## Boot -- initramfs

| Fichier | Lignes | Role |
|---|---:|---|
| `initramfs-init` | 314 | Init principal (type zbm). |
| `initramfs-stream-init` | 135 | Init variante stream. |

---

## Runtime

| Fichier | Lignes | Role |
|---|---:|---|
| `system/zbm-startup` | 315 | Service de demarrage. |
| `python-interface.py` | 5122 | TUI Textual — 36 classes dont 15 nouvelles (voir ci-dessous). |

---

## Classes Python (python-interface.py)

### Nouvelles classes de gestion independantes (miroir Python des scripts bash)

| Classe | Lignes | Role |
|---|---|---|
| `ConfigManager` | ~135 | Lit/ecrit deploy/config.sh directement (pur Python, sans bash). Parse KEY="val", expose get_systems(), kernel_label, kernel_ver, init_type, etc. Methode set() pour mise a jour via sed. |
| `BootPoolLocator` | ~58 | Localise le mountpoint de boot_pool : zfs mount -> /boot -> import temporaire. Methode mount_temp() pour montage transitoire. |
| `KernelEntry` | ~45 | Dataclass : path, label, date, kver, size, has_modules, modules_path, is_active, meta. Proprietes : size_human, date_display, age_days. |
| `KernelScanner` | ~90 | Scan des kernels dans boot_pool. Miroir Python de zbm_select_kernel(). scan() retourne KernelEntry[] tries par date decroissante. scan_initramfs(), latest_kernel(), find_by_label(), initramfs_for_kernel(). |
| `DatasetManager` | ~188 | Verification et creation des datasets ZFS. datasets_for_system(), status(), create(), create_for_system(), detect_systems_from_zfs(). Miroir de datasets-check.sh. |
| `PoolManager` | ~68 | Etat des pools : list_imported(), list_importable(), info(), import_pool(). |
| `KernelInstallManager` | ~192 | Installation kernel + modules depuis le live. find_kernel_in_live(), find_modules_in_live(), install() (yield log), delete(). Ecrit KERNEL_VER dans config.sh. Miroir de kernel.sh. |
| `InitramfsBuilder` | ~281 | Construction d'un initramfs. build() pour zbm/zbm-stream (cpio+zstd direct) ou minimal (dracut). Miroir de initramfs.sh sans dependance bash. |
| `RootfsInstallManager` | ~70 | Installation rootfs.sfs dans boot_pool. find_rootfs_on_live(), install(). Miroir de rootfs.sh. |
| `DeployOrchestrator` | ~111 | Orchestrateur : step_detect(), step_datasets(), step_kernel_info(), step_initramfs_info(), step_rootfs_info(), step_presets_info(), full_status(). Miroir de deploy.sh. |

### Nouveaux ecrans TUI

| Ecran | Role |
|---|---|
| `KernelSelectScreen` | Liste tous les kernels installes dans boot_pool avec label/date/kver/taille/modules/actif. Boutons : Activer symlink (vmlinuz + initrd.img + modules.sfs + config.sh), Supprimer, Installer depuis le live (-> KernelInstallScreen). |
| `KernelInstallScreen` | Formulaire d'installation kernel : label, chemin source, chemin modules. Bouton "Detecter sources" : auto-detection dans le live. |
| `DeployScreen` | Tableau de bord complet du deploiement. Table d'etat (pools/kernels/initramfs/rootfs/presets). Boutons pour chaque etape (1-9). Affiche config.sh active. Log en temps reel. |
| `InitramfsScreen` | Construction d'un initramfs : choix du type (zbm/zbm-stream/minimal/custom), kver, liste des initramfs installes, suppression. |
| `RootfsScreen` | Installation rootfs : liste les .sfs disponibles (live + boot_pool), formulaire systeme/label/source. |

### Ecrans precedents (inchanges)

StreamScreen, PresetConfigScreen, ProfileEditScreen, SnapshotScreen,
HotSwapScreen, CoherenceScreen, FailsafeScreen, MainScreen, ZBMApp.

MainScreen : 2 nouveaux boutons — **Kernels** (-> KernelSelectScreen)
et **Deploiement** (-> DeployScreen).

---

## Failsafe et maintenance

| Fichier | Lignes | Role |
|---|---:|---|
| `create-failsafe.sh` | 245 | Cree le failsafe fige dans boot_pool/images/failsafe/. |
| `update-failsafe-links.sh` | 128 | Met a jour les symlinks failsafe. |
| `cron-tasks.sh` | 479 | Planification snapshots ZFS. |

---

## Invariants architecture

- `canmount=noauto` sur tous les `fast_pool/*`
- Montage : `mount -t zfs <ds> <chemin>` + guard `mountpoint -q`
- Kernels et modules independants des systemes (pas de system dans le nom)
- Un `fast_pool/overlay-<s>` par systeme, isolation complete
- `SYSTEMS=(...)` dans config.sh = source de verite unique
- `boot_pool` localise dynamiquement (jamais /boot code en dur)
- Initramfs construit sans dracut (types zbm/zbm-stream) -- zero kver live
- `KERNEL_VER` ecrite par kernel.sh dans config.sh -- jamais `uname -r` du live
- config.sh genere en pure ASCII

---

## Totaux

| Categorie | Fichiers | Lignes |
|---|---:|---:|
| Deploy (deploy.sh + config.sh) | 2 | 316 |
| Bibliotheque lib/ (avec zbm_select_kernel) | 13 | 3 679 |
| Boot (initramfs) | 2 | 449 |
| Runtime (startup + TUI Python) | 2 | 5 437 |
| Failsafe et maintenance | 3 | 852 |
| **Total** | **22** | **10 822** |
