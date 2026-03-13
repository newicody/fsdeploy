#!/bin/bash
# =============================================================================
# deploy/config.sh
#
# Source de verite de la configuration ZFSBootMenu.
# Genere par lib/detect.sh -- editable manuellement.
# Source par deploy.sh et tous les scripts lib/*.sh.
#
# Apres modification de SYSTEMS :
#   etape 2 (datasets-check.sh) pour creer les datasets
#   etape 7 (presets.sh)        pour generer les entrees de boot
# =============================================================================

# -----------------------------------------------------------------------------
# SYSTEMES
#
# Un systeme = jeu de datasets ZFS isoles :
#   fast_pool/overlay-<s>   canmount=noauto  (upper OverlayFS)
#   fast_pool/var-<s>       canmount=noauto  mountpoint=/var
#   fast_pool/log-<s>       canmount=noauto  mountpoint=/var/log
#   fast_pool/tmp-<s>       canmount=noauto  mountpoint=/tmp
#
# "failsafe" est reserve -- ne pas l'ajouter ici.
# Noms valides : lettres, chiffres, tirets, underscores. Pas d'espace.
# -----------------------------------------------------------------------------
SYSTEMS=("systeme1")

# -----------------------------------------------------------------------------
# POOLS ZFS
# -----------------------------------------------------------------------------
BOOT_POOL="boot_pool"
FAST_POOL="fast_pool"
DATA_POOL="data_pool"

# -----------------------------------------------------------------------------
# MATERIEL -- rempli par lib/detect.sh
#
# NVME_A         : NVMe portant boot_pool + partition EFI
# NVME_B         : NVMe portant fast_pool (entier, sans partitions)
# EFI_PART       : partition vfat EFI  ex: /dev/nvme0n1p1
# BOOT_POOL_PART : partition ZFS boot_pool  ex: /dev/nvme0n1p2
# DATA_DISKS     : disques SATA pour data_pool (RAIDZ2)
# -----------------------------------------------------------------------------
NVME_A=""
NVME_B=""
EFI_PART=""
BOOT_POOL_PART=""
# Points de montage live (correspondant à ZBM_BOOT="/mnt/zbm/boot")
# Valeurs réelles sur le système installé — utilisées par zbm.sh uniquement
EFI_MNT="/boot/efi"
BOOT_MNT="/boot"
RAIDZ_TYPE="raidz2"
DATA_DISKS=()

# -----------------------------------------------------------------------------
# KERNEL
#
# KERNEL_LABEL : identifiant libre du kernel dans boot_pool.
#                Format recommande : <type>-<version>  ex: generic-6.12
#                Fichier : boot_pool/images/kernels/kernel-<KERNEL_LABEL>-<date>
#                Vide = lib/kernel.sh demandera interactivement.
#
# KERNEL_VER   : version exacte  ex: 6.12.0-4-amd64
#                Ecrite automatiquement par kernel.sh apres installation.
#                Utilisee par initramfs.sh (type minimal) et presets.sh.
#                Ne pas modifier manuellement sauf necessite.
# -----------------------------------------------------------------------------
KERNEL_LABEL=""
KERNEL_VER=""

# -----------------------------------------------------------------------------
# INITRAMFS
#
# INIT_TYPE : type d'initramfs a construire.
#   zbm         Init complet : overlay + pivot_root + Python TUI + stream
#   zbm-stream  Variante stream seule, sans TUI Python
#   minimal     Init natif noyau (necessite dracut + KERNEL_VER)
#   custom-<n>  Init personnalise
#
#   Vide = lib/initramfs.sh demandera interactivement.
# -----------------------------------------------------------------------------
INIT_TYPE="zbm"

# -----------------------------------------------------------------------------
# ROOTFS
#
# ROOTFS_LABEL : label commun a tous les rootfs.
#                Format : <distro>[-<variant>]  ex: gentoo  arch  debian-base
#                Fichier : rootfs-<systeme>-<ROOTFS_LABEL>-<date>.sfs
#
# ROOTFS_SRC   : source du rootfs a installer.
#                "auto"  = cherche *.sfs sur le support live
#                chemin  = chemin absolu vers le fichier .sfs source
# -----------------------------------------------------------------------------
ROOTFS_LABEL="gentoo"
ROOTFS_SRC="auto"

# -----------------------------------------------------------------------------
# STREAM YOUTUBE
# -----------------------------------------------------------------------------
STREAM_KEY=""
STREAM_RESOLUTION="1920x1080"
STREAM_FPS=30
STREAM_BITRATE="4500k"
STREAM_DELAY_SEC=30

# -----------------------------------------------------------------------------
# RESEAU
#
# NETWORK_MODE  : dhcp | static | none
# NETWORK_IFACE : interface reseau (auto = detection automatique)
# -----------------------------------------------------------------------------
NETWORK_MODE="dhcp"
NETWORK_IFACE="auto"
# Si NETWORK_MODE=static, decommenter et remplir :
# NETWORK_IP="192.168.1.10/24"
# NETWORK_GW="192.168.1.1"
# NETWORK_DNS="1.1.1.1"

# -----------------------------------------------------------------------------
# REGLE MOUNTPOINTS ZFS -- ne pas modifier
#
# Tous les datasets fast_pool/* ont canmount=noauto.
# La propriete mountpoint= est documentation uniquement.
# Montage reel : initramfs-init via "mount -t zfs <ds> <chemin>"
# avec guard "mountpoint -q" anti-double-montage.
# Jamais de "zfs mount -a" ni "zfs set mountpoint" au runtime.
# -----------------------------------------------------------------------------
