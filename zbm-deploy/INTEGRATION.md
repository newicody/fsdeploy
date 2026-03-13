# ZBM — INTÉGRATION COMPLÈTE
**i5-11400 / Gigabyte Z490 UD / 128 GB DDR4**
**2× NVMe 1 TB · 5× SATA 4 TB**

---

## 1. CORRECTIONS IDENTIFIÉES DANS LE PROJET ORIGINAL

### 1.1 Failsafe — erreurs majeures (corrigées dans create-failsafe.sh)
| # | Problème | Correction |
|---|----------|------------|
| 1 | Compilait un kernel depuis zéro | Copie d'un kernel existant uniquement |
| 2 | initramfs "spécial recovery" autonome | initramfs normal du système source copié |
| 3 | L'UI était censée réinstaller le failsafe | L'UI ne touche JAMAIS à `/boot/images/failsafe/` |
| 4 | Pas de vérification MD5 des copies | MD5 vérifié à la copie ET à la fin |
| 5 | Fichiers copiés avec droits écriture | chmod 444 — protection accidentelle |
| 6 | Aucune sauvegarde de l'existant | Backup automatique `.bak.TIMESTAMP` |

### 1.2 Snapshot manager — erreurs (corrigées dans cron-tasks.sh)
| # | Problème | Correction |
|---|----------|------------|
| 1 | `fast_pool/overlay` snapshoté *par système* → duplicats | overlay snapshoté une seule fois par set |
| 2 | `prune` liste tous les `.zst` mélangés → comptage faux | prune par *set* (timestamp unique) |
| 3 | `restore` utilise `zfs rollback` sans vérifier l'existence | vérification préalable + message clair |
| 4 | Pas de vérification que le dataset est démonté avant restore | arrêt propre si dataset actif |
| 5 | `OVERLAY_DS` hardcodé sans variable système | isolé dans les variables, commenté |

### 1.3 Interface Python — erreurs (corrigées dans python-interface.py)
| # | Problème | Correction |
|---|----------|------------|
| 1 | `snap['file'].name` sur une string → AttributeError | `Path(snap['file']).name` |
| 2 | `table.cursor_row` n'existe pas dans Textual 0.47+ | `table.cursor_coordinate.row` |
| 3 | `table.get_row(row)` → API incorrecte | `table.get_row_at(row_index)` |
| 4 | Aucun import en tête du fichier | imports complets ajoutés |
| 5 | L'UI pouvait appeler le failsafe | `protected: true` lu depuis le preset, entrée désactivée dans l'UI |
| 6 | Pas de gestion d'erreur si Textual absent | try/import avec message explicite |

### 1.4 Cron — erreurs (corrigées dans cron-tasks.sh)
| # | Problème | Correction |
|---|----------|------------|
| 1 | `for sys in ...; do` inline dans crontab → invalide | script wrapper dédié |
| 2 | Pas de rotation des logs cron | logrotate configuré |
| 3 | Service watch écrit un JSON sans protection | écriture atomique via tmpfile |

### 1.5 MANQUANT — initramfs init (ajouté : initramfs-init)
Le projet ne contient **aucun init initramfs**. C'est la pièce la plus critique :
sans lui, aucun système ne boote. Ajouté complet dans `initramfs-init`.

---

## 2. ARCHITECTURE MATÉRIELLE

```
┌─────────────────────────────────────────────────────────────────┐
│  i5-11400 (UHD 730 — QSV disponible pour ffmpeg)               │
│  Z490 UD — 128 GB DDR4                                          │
│                                                                  │
│  M.2_1 (CPU PCIe 3.0 x4) ──► NVMe-A 1 TB ──► boot_pool        │
│  M.2_2 (CPU PCIe 3.0 x4) ──► NVMe-B 1 TB ──► fast_pool        │
│                                                                  │
│  SATA1 ──► 4 TB ─┐                                              │
│  SATA2 ──► 4 TB  │                                              │
│  SATA3 ──► 4 TB  ├──► data_pool (RAIDZ2, ~12 TB utiles)        │
│  SATA4 ──► 4 TB  │                                              │
│  SATA5 ──► 4 TB ─┘                                              │
└─────────────────────────────────────────────────────────────────┘
```

### Partitionnement NVMe-A (boot_pool)
```
/dev/nvme0n1p1  550 MB   EFI System Partition  (vfat, mountpoint=/boot/efi)
/dev/nvme0n1p2  reste    boot_pool             (ZFS)
```

### Partitionnement NVMe-B (fast_pool)
```
/dev/nvme1n1    1 TB     fast_pool             (ZFS, partition unique)
```

---

## 3. POOLS ZFS

### 3.1 Création des pools

```bash
# boot_pool — NVMe-A, partition 2
# ashift=13 : secteurs 4K natifs + préfetch NVMe
zpool create \
    -o ashift=13 \
    -O compression=zstd \
    -O atime=off \
    -O xattr=sa \
    -O dnodesize=auto \
    -O mountpoint=/boot \
    boot_pool /dev/disk/by-id/nvme-<A>-part2

# fast_pool — NVMe-B entier
zpool create \
    -o ashift=13 \
    -O compression=zstd \
    -O atime=off \
    -O xattr=sa \
    -O dnodesize=auto \
    -O mountpoint=none \
    fast_pool /dev/disk/by-id/nvme-<B>

# data_pool — 5× SATA en RAIDZ2 (2 disques de parité)
# ashift=12 : secteurs 4K natifs SATA
zpool create \
    -o ashift=12 \
    -O compression=zstd \
    -O atime=off \
    -O xattr=sa \
    -O mountpoint=none \
    data_pool raidz2 \
        /dev/disk/by-id/ata-<1> \
        /dev/disk/by-id/ata-<2> \
        /dev/disk/by-id/ata-<3> \
        /dev/disk/by-id/ata-<4> \
        /dev/disk/by-id/ata-<5>
```

### 3.2 Datasets

```bash
# ── boot_pool ──────────────────────────────────────────────────
# Le pool lui-même a mountpoint=/boot
# Pas de dataset intermédiaire — on travaille directement dans /boot

# ── fast_pool ──────────────────────────────────────────────────
# Un seul dataset ZFS par système — architecture overlay pure
# /var /tmp /etc sont dans le lower (squashfs) + upper (overlay)
zfs create -o canmount=noauto -o mountpoint=none  fast_pool/overlay-systeme1
zfs create -o canmount=noauto -o mountpoint=none  fast_pool/overlay-systeme2
zfs create -o canmount=noauto -o mountpoint=none  fast_pool/overlay-failsafe

# ── data_pool ──────────────────────────────────────────────────
zfs create -o mountpoint=/home       data_pool/home
zfs create -o mountpoint=none        data_pool/archives
zfs create -o mountpoint=none        data_pool/archives/systeme1
zfs create -o mountpoint=none        data_pool/archives/systeme2
```

### 3.3 Structure de boot_pool (= /boot)

```
/boot/
├── vmlinuz          → images/kernels/vmlinuz-6.19-gentoo     (symlink actif)
├── initrd.img       → images/initramfs/initramfs-6.19-gentoo.img
├── rootfs.sfs       → images/rootfs/systeme1-rootfs.sfs
│
├── images/
│   ├── kernels/
│   │   ├── vmlinuz-6.19-gentoo
│   │   └── vmlinuz-6.18-gentoo
│   ├── initramfs/
│   │   ├── initramfs-6.19-gentoo.img
│   │   └── initramfs-6.18-gentoo.img
│   ├── rootfs/
│   │   ├── systeme1-rootfs.sfs
│   │   └── systeme2-rootfs.sfs
│   ├── modules/
│   │   ├── modules-6.19-gentoo.sfs
│   │   └── modules-6.18-gentoo.sfs
│   ├── startup/
│   │   └── python-3.11.sfs
│   └── failsafe/                  ← géré par create-failsafe.sh UNIQUEMENT
│       ├── vmlinuz-failsafe
│       ├── initramfs-failsafe.img
│       ├── modules-failsafe.sfs
│       ├── rootfs-failsafe.sfs
│       └── failsafe.meta
│
├── presets/
│   ├── systeme1.json
│   ├── systeme2.json
│   └── failsafe.json              ← protected:true, jamais modifié par l'UI
│
├── snapshots/
│   ├── systeme1/
│   │   └── set-20250305-143022/
│   │       ├── var.zst
│   │       ├── log.zst
│   │       └── overlay.zst
│   └── systeme2/
│
├── logs/
│   ├── systeme1/
│   ├── systeme2/
│   └── failsafe/
│
└── EFI/
    └── ZBM/
        ├── vmlinuz.EFI
        └── config.yaml
```

---

## 4. SÉQUENCE DE BOOT

```
UEFI
  │
  ▼
EFI/ZBM/vmlinuz.EFI  ─── ZFSBootMenu
  │
  │  Lit /boot/presets/*.json
  │  Affiche la liste (priority croissant, failsafe en dernier)
  │
  ▼
Kernel sélectionné + initramfs
  │
  ▼
initramfs-init  (voir initramfs-init)
  │
  ├── parse /proc/cmdline
  ├── zfs import pools
  ├── monte boot_pool
  ├── monte rootfs.sfs  → /mnt/lower1
  │
  ├── [boot normal]
  │     upper  = fast_pool/overlay  (rw, ZFS)
  │     workdir = fast_pool/overlay/.work
  │     merged  = /mnt/merged  → pivot_root
  │     puis monte var + log dans le système
  │
  └── [boot failsafe]
        lower   = rootfs-failsafe.sfs  (squashfs RO)
        upper   = fast_pool/overlay-failsafe/upper  (ZFS RW, persistant)
        workdir = fast_pool/overlay-failsafe/.work
        merged  = /mnt/merged  → pivot_root
        # /var /tmp → dans le lower + écrits dans upper (pas de datasets séparés)

  ▼
Système en cours d'exécution
  │
  └── OpenRC → zbm-startup → Réseau DHCP + Python TUI (Textual)
```

---

## 5. OVERLAY — DÉTAIL

### Boot normal (systeme1)
```
OverlayFS:
  lowerdir  = /mnt/rootfs        ← squashfs monté en RO
  upperdir  = /mnt/fast/upper    ← fast_pool/overlay monté en RW
  workdir   = /mnt/fast/.work    ← dans fast_pool/overlay
  merged    = /                  ← après pivot_root
```

### Boot failsafe
```
OverlayFS (identique au boot normal) :
  lowerdir  = /mnt/lower                       ← rootfs-failsafe.sfs (squashfs RO)
  upperdir  = /mnt/fast/upper                  ← fast_pool/overlay-failsafe/upper (ZFS RW)
  workdir   = /mnt/fast/.work                  ← fast_pool/overlay-failsafe/.work
  merged    = /                                ← après pivot_root

  /var /tmp → écrits dans upper (overlay-failsafe) — pas de datasets séparés
```

Le failsafe démarre exactement comme un système normal.
L'isolation est garantie par le dataset `fast_pool/overlay-failsafe` dédié.


---

## 6. PRESETS ZFSBOOTMENU

### Format d'un preset (lu par l'UI Python, interprété pour ZBM)

```json
{
    "_comment": "...",
    "_generated": "ISO8601",
    "name": "systeme1",
    "label": "Système 1  [6.19-gentoo]",
    "priority": 10,
    "protected": false,
    "kernel": "/boot/images/kernels/vmlinuz-6.19-gentoo",
    "initramfs": "/boot/images/initramfs/initramfs-6.19-gentoo.img",
    "modules": "/boot/images/modules/modules-6.19-gentoo.sfs",
    "rootfs": "/boot/images/rootfs/systeme1-rootfs.sfs",
    "var_dataset": "fast_pool/var-systeme1",
    "log_dataset": "fast_pool/log-systeme1",
    "overlay_dataset": "fast_pool/overlay",
    "cmdline": "ro quiet loglevel=3 zbm_system=systeme1"
}
```

### Règle de priorité ZBM
```
systeme1   priority: 10   → premier dans le menu
systeme2   priority: 20   → deuxième
failsafe   priority: 999  → toujours dernier, protected: true
```

---

## 7. FICHIERS PRODUITS

| Fichier | Rôle | Déclencheur |
|---------|------|-------------|
| `create-failsafe.sh` | Copie figée du failsafe | **Manuel uniquement** |
| `initramfs-init` | Init initramfs universel | Embarqué dans chaque initramfs |
| `cron-tasks.sh` | Gestion snapshots | Manuel ou cron via wrapper |
| `python-interface.py` | TUI Textual complète | OpenRC au démarrage |
| `zbm-startup` | Service OpenRC : réseau, stream, TUI | `rc-update add zbm-startup default` |
| `cron-tasks.sh` | Tâches cron (snapshots, nettoyage) | Manuel à l'install |

---

## 8. RÈGLES D'INTÉGRATION — ABSOLUES

```
┌───────────────────────────────────────────────────────────────┐
│  L'UI Python PEUT :                                           │
│    - Lire failsafe.meta (affichage info)                      │
│    - Lire failsafe.json preset (affichage)                    │
│    - Régénérer ZFSBootMenu (config EFI, kernels normaux)      │
│    - Gérer les snapshots systeme1/systeme2                    │
│    - Modifier les presets systeme1.json, systeme2.json        │
│                                                               │
│  L'UI Python NE PEUT PAS :                                    │
│    - Modifier /boot/images/failsafe/ (protection chmod 444)   │
│    - Modifier failsafe.json (protected:true, vérifié à l'UI)  │
│    - Snapshoter au nom du failsafe                            │
│    - Lancer create-failsafe.sh                             │
└───────────────────────────────────────────────────────────────┘
```

---

## 9. STREAM YOUTUBE — x264 SOFT (i5-11400, sans GPU dédié)

Le i5-11400 (6c/12t) gère sans problème un encode x264 `veryfast` en 1080p30
en parallèle du système. Pas besoin de QSV pour l'instant.

```bash
# Stream YouTube x264 soft depuis framebuffer
ffmpeg -y \
    -f fbdev   -framerate 30 -i /dev/fb0 \
    -f alsa    -i hw:0,0 \
    -c:v libx264 -preset veryfast -tune zerolatency \
    -b:v 4500k -maxrate 4500k -bufsize 9000k \
    -pix_fmt yuv420p \
    -g 60 -keyint_min 60 \
    -c:a aac -b:a 128k -ar 44100 \
    -f flv "rtmp://a.rtmp.youtube.com/live2/$STREAM_KEY"

# Charge CPU estimée sur i5-11400 à veryfast 1080p30 : ~30-40%
# (laisse largement de la marge pour le reste du système)
```

Quand un GPU sera ajouté : remplacer `-c:v libx264 -preset veryfast`
par `-c:v h264_qsv -preset veryfast` et ajouter `-init_hw_device qsv=qsv:hw`.
Le rootfs Gentoo devra alors inclure `media-libs/intel-mediasdk`.

---
*Document généré par create-failsafe.sh integration review*
*Hardware : i5-11400 / Z490 UD / 2× NVMe 1TB / 5× SATA 4TB*
