# zbm-deploy — ZFSBootMenu Custom

> Architecture overlay pure : squashfs lower + ZFS upper + pivot_root
> i5-11400 / Z490 UD — NVMe-A (boot_pool) + NVMe-B (fast_pool) + 5×SATA (data_pool)

---

## STRUCTURE DU PROJET

```
zbm-deploy/
├── README.md                        ← ce fichier
├── ARCHITECTURE.md                  ← architecture complète (pools, datasets, boot)
├── FILES.md                         ← convention de nommage des images
├── INTEGRATION.md                   ← intégration Gentoo / OpenRC
│
├── deploy/                          ← scripts de déploiement (lancer depuis live Debian)
│   ├── config.sh                    ← configuration persistée (NVMe, pools, label…)
│   ├── deploy.sh                    ← ★ POINT D'ENTRÉE — menu interactif
│   └── lib/
│       ├── mounts.sh                ← source de vérité : points de montage
│       ├── naming.sh                ← nommage images + zbm_locate_boot() + fonctions ZFS
│       ├── detect.sh                ← étape 1 : détection NVMe / EFI / pools
│       ├── datasets-check.sh        ← étape 2 : vérif/création datasets ZFS
│       ├── rootfs.sh                ← étape 3 : installation rootfs.sfs
│       ├── python-sfs.sh            ← étape 4 : construction python.sfs (venv+textual)
│       ├── initramfs.sh             ← étape 5 : construction initramfs custom (cpio)
│       ├── zbm.sh                   ← étape 6 : installation ZFSBootMenu EFI + UEFI
│       ├── presets.sh               ← étape 7 : génération presets JSON + symlinks
│       ├── failsafe.sh              ← étape 8 : installation images failsafe
│       ├── coherence.sh             ← vérification cohérence datasets/presets/symlinks
│       ├── import-mount.sh          ← inspection/chroot des pools
│       ├── kernel.sh                ← extraction kernel + modules depuis rootfs
│       └── umount.sh                ← démontage propre
│
├── initramfs-init                   ← init custom (overlay + pivot_root) — embarqué dans initramfs
├── initramfs-stream-init            ← init variante stream YouTube
│
├── create-failsafe.sh               ← création images failsafe (appelé par failsafe.sh)
├── update-failsafe-links.sh         ← mise à jour symlinks failsafe
├── cron-tasks.sh                    ← installation cron + service zbm-startup dans le rootfs
│
├── system/
│   └── zbm-startup                  ← service OpenRC : réseau DHCP + stream YouTube + TUI
│
└── python-interface.py              ← TUI Textual complète (déployée dans python.sfs)
```

---

## DÉPLOIEMENT

### Prérequis
- Boot depuis Debian Live (amd64)
- ZFS installé dans le live : `apt install zfsutils-linux`
- Pools ZFS créés (voir ARCHITECTURE.md)

### Lancement
```bash
git clone / décompresser zbm-deploy.zip
cd zbm-deploy
bash deploy/deploy.sh
```

Le menu propose 8 étapes numérotées + options de maintenance.

---

## CHEMINS D'INSTALLATION

### Sur boot_pool (monté sur /boot dans le système installé)
```
/boot/
├── boot/                            ← symlinks actifs ZFSBootMenu
│   ├── vmlinuz      → ../images/kernels/kernel-<label>-<date>
│   ├── initrd.img   → ../images/initramfs/initramfs-<label>-<date>.img
│   ├── modules.sfs  → ../images/modules/modules-<label>-<date>.sfs
│   └── rootfs.sfs   → ../images/rootfs/rootfs-<sys>-<label>-<date>.sfs
├── images/
│   ├── kernels/     ← kernel-<label>-<date>
│   ├── initramfs/   ← initramfs-<label>-<date>.img  (contient initramfs-init)
│   ├── modules/     ← modules-<label>-<date>.sfs
│   ├── rootfs/      ← rootfs-<sys>-<label>-<date>.sfs  (squashfs Gentoo)
│   ├── startup/     ← python-<ver>-<date>.sfs
│   └── failsafe/    ← kernel, initramfs, modules, rootfs figés
├── presets/         ← systeme1.json, systeme2.json, failsafe.json
├── hooks/           ← zbm-hook-normal.sh (exécuté par ZBM avant kexec)
├── snapshots/       ← créé par python-interface.py au premier snapshot
└── efi/EFI/ZBM/     ← vmlinuz.EFI, vmlinuz-backup.EFI (ZFSBootMenu)
```

### Dans le rootfs Gentoo (installé par cron-tasks.sh)
```
/etc/init.d/zbm-startup              ← service OpenRC (copié depuis system/zbm-startup)
/etc/cron.d/zbm-snapshots            ← planification cron
/usr/local/bin/zbm-run-scheduled.py  ← exécuteur de profils snapshot
/usr/local/bin/zbm-monthly-archive.sh← archivage mensuel vers data_pool
/etc/logrotate.d/zbm                 ← rotation logs
```

### Dans python.sfs (squashfs monté sur /mnt/python au boot)
```
/mnt/python/
├── venv/bin/python3                 ← Python + Textual installés
└── etc/zfsbootmenu/
    └── python_interface.py          ← TUI Textual (copié depuis python-interface.py)
```

### Datasets ZFS
```
boot_pool                            ← mountpoint=legacy, bootfs=boot_pool
boot_pool/images                     ← dataset enfant (monté automatiquement)

fast_pool/overlay-systeme1           ← canmount=noauto, mountpoint=none
fast_pool/overlay-systeme2           ← idem
fast_pool/overlay-failsafe           ← idem

data_pool/home                       ← /home (partagé entre systèmes)
data_pool/archives/systeme1          ← snapshots cold storage
data_pool/archives/systeme2          ← idem
```

### Partition EFI (vfat)
```
/boot/efi/EFI/ZBM/
├── vmlinuz.EFI                      ← ZFSBootMenu (entrée UEFI principale)
└── vmlinuz-backup.EFI               ← Backup (entrée UEFI secondaire)
```

---

## FLUX DE BOOT

```
UEFI → vmlinuz.EFI (ZFSBootMenu)
  └── importe boot_pool
      lit presets/*.json → menu interactif
      kexec → kernel + initramfs-init

initramfs-init
  ├── importe fast_pool
  ├── monte boot_pool/images
  ├── monte rootfs-<s>.sfs  → /mnt/lower   (lower, ro)
  ├── monte overlay-<s>     → /mnt/fast     (upper, rw)
  ├── assembleoverlayfs     → /mnt/merged
  ├── bind /mnt/boot        → /mnt/merged/mnt/boot
  ├── pivot_root /mnt/merged
  └── exec /sbin/init (OpenRC)
        └── zbm-startup
              ├── DHCP sur e1000e (Intel I219-V)
              ├── monte python.sfs → /mnt/python
              ├── stream YouTube (ffmpeg, si preset configuré)
              └── TUI Textual sur TTY1
```

---

## CMDLINE KERNEL (dans presets/*.json)

```
zbm_system=systeme1
zbm_rootfs=/boot/images/rootfs/rootfs-systeme1-gentoo-20250310.sfs
zbm_modules=/boot/images/modules/modules-generic-6.12-20250310.sfs
zbm_overlay=fast_pool/overlay-systeme1
```

---

## FICHIERS CLÉS PAR CONTEXTE

| Contexte | Fichier | Action |
|----------|---------|--------|
| Déploiement initial | `deploy/deploy.sh` | `bash deploy/deploy.sh` |
| Ajout système | `deploy/lib/datasets-check.sh` | Option du menu |
| Nouveau kernel | `deploy/lib/kernel.sh` | Option du menu |
| Nouveau rootfs | `deploy/lib/rootfs.sh` | Option du menu |
| Rebuild initramfs | `deploy/lib/initramfs.sh` | Option du menu |
| Mise à jour ZBM | `deploy/lib/zbm.sh` | Option du menu |
| Vérification cohérence | `deploy/lib/coherence.sh` | Option du menu |
| Snapshots / restauration | `python-interface.py` | TUI au boot (TTY1) |
| Cron snapshots | `cron-tasks.sh` | Installer dans le rootfs |
| Failsafe figé | `create-failsafe.sh` | Manuel uniquement |
