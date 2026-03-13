#!/bin/bash
# =============================================================================
# lib/mounts.sh — SOURCE DE VÉRITÉ UNIQUE pour tous les points de montage
#
# RÈGLE ABSOLUE : tout script du répertoire deploy/ source ce fichier.
# Ne jamais hardcoder /mnt/zbm-live, /mnt/zbm, /mnt/boot dans les scripts
# deploy/ — utiliser les constantes ci-dessous.
#
# ─── TABLE DES POINTS DE MONTAGE ─────────────────────────────────────────────
#
#   Contexte     │ boot_pool          │ boot_pool/images        │ Altroot ZFS  │ EFI
#   ─────────────┼────────────────────┼─────────────────────────┼──────────────┼──────────────────
#   Live deploy  │ /mnt/zbm/boot      │ /mnt/zbm/boot/images    │ /mnt/zbm     │ /mnt/zbm/boot/efi
#   Initramfs    │ /mnt/boot          │ /mnt/boot/images        │ N/A          │ N/A
#   Système réel │ /boot              │ /boot/images            │ /            │ /boot/efi
#
# ─── SYMLINKS ZBM ────────────────────────────────────────────────────────────
#
#   ZBM importe boot_pool (bootfs=boot_pool), le monte à une tmpdir, puis
#   cherche <tmpdir>/boot/vmlinuz.
#   → Les symlinks actifs sont dans boot_pool/boot/ (= $ZBM_BOOT/boot/).
#   → Les initramfs symlinks sont $ZBM_BOOT/boot/initrd.img, etc.
#   → Les images sont dans $ZBM_BOOT/images/ (via dataset boot_pool/images).
#
#   Chemins complets sur le live :
#     $ZBM_BOOT/boot/vmlinuz      → ../images/kernels/kernel-<label>-<date>
#     $ZBM_BOOT/boot/initrd.img   → ../images/initramfs/initramfs-<label>-<date>.img
#     $ZBM_BOOT/boot/modules.sfs  → ../images/modules/modules-<label>-<date>.sfs
#     $ZBM_BOOT/boot/rootfs.sfs   → ../images/rootfs/rootfs-<sys>-<label>-<date>.sfs
#
# ─── UTILISATION ─────────────────────────────────────────────────────────────
#
#   source "$(dirname "$0")/lib/mounts.sh"        # depuis deploy.sh
#   source "$(dirname "$0")/mounts.sh"            # depuis lib/*.sh
#
#   ZBM_ALTROOT   → altroot pour zpool import -R
#   ZBM_BOOT      → point de montage de boot_pool
#   ZBM_BOOT_LINKS→ répertoire des symlinks ZBM (= $ZBM_BOOT/boot)
#   ZBM_IMAGES    → répertoire des images    (= $ZBM_BOOT/images)
#   ZBM_EFI       → partition EFI            (= $ZBM_BOOT/efi)
#   ZBM_PRESETS   → répertoire des presets   (= $ZBM_BOOT/presets)
# =============================================================================

# Altroot ZFS : préfixe pour zpool import -R (fast_pool, data_pool)
ZBM_ALTROOT="/mnt/zbm"

# boot_pool est importé sans -R (mountpoint=legacy, montage explicite toujours)
# Sur le live, /boot appartient au Debian live → on utilise /mnt/zbm/boot
ZBM_BOOT="${ZBM_ALTROOT}/boot"

# Sous-répertoires dérivés — NE PAS modifier individuellement
ZBM_BOOT_LINKS="${ZBM_BOOT}/boot"      # Symlinks ZBM (vmlinuz, initrd.img, …)
ZBM_IMAGES="${ZBM_BOOT}/images"        # Dataset boot_pool/images
ZBM_EFI="${ZBM_BOOT}/efi"             # Partition EFI vfat
ZBM_PRESETS="${ZBM_BOOT}/presets"      # Presets JSON
ZBM_HOOKS="${ZBM_BOOT}/hooks"          # Hooks boot

# Exporter pour les sous-processus
export ZBM_ALTROOT ZBM_BOOT ZBM_BOOT_LINKS ZBM_IMAGES ZBM_EFI ZBM_PRESETS ZBM_HOOKS
