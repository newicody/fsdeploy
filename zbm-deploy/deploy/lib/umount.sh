#!/bin/bash
# =============================================================================
# lib/umount.sh
# Démontage propre dans l'ordre inverse du montage.
#
# Usage : bash lib/umount.sh [--altroot /mnt/zbm] [--dry-run]
# =============================================================================

set -euo pipefail

_MOUNTS_SH="$(dirname "${BASH_SOURCE[0]}")/mounts.sh"
[[ -f "$_MOUNTS_SH" ]] && source "$_MOUNTS_SH"


GREEN='\033[1;32m'; YELLOW='\033[1;33m'; DIM='\033[2m'; BOLD='\033[1m'; NC='\033[0m'

ok()   { echo -e "  ${GREEN}✅${NC} $*"; }
warn() { echo -e "  ${YELLOW}⚠️ ${NC} $*"; }
skip() { echo -e "  ${DIM}  ↷ $* (non monté)${NC}"; }
head() { echo -e "\n${BOLD}── $* ──${NC}"; }

ALTROOT="${ZBM_ALTROOT:-/mnt/zbm}"
DRY_RUN=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --altroot) ALTROOT="$2"; shift 2 ;;
        --dry-run) DRY_RUN=1;   shift ;;
        *) echo "Argument inconnu : $1"; exit 1 ;;
    esac
done

[[ "$ALTROOT" == "/" ]] || ALTROOT="${ALTROOT%/}"

X() {
    [[ $DRY_RUN -eq 1 ]] && echo -e "  ${DIM}[dry]${NC} $*" || "$@"
}

umount_if_mounted() {
    local mp="$1"
    if mountpoint -q "$mp" 2>/dev/null; then
        # Essai normal, puis lazy si refusé (busy) — évite les états incohérents ZFS
        if X umount "$mp" 2>/dev/null; then
            ok "démonté : $mp"
        elif X umount -l "$mp" 2>/dev/null; then
            warn "démonté (lazy) : $mp — vérifier que rien ne l'utilise encore"
        else
            warn "umount échoué : $mp (processus en cours ?)"
        fi
    else
        skip "$mp"
    fi
}

# Ordre inverse du montage
head "Démontage des squashfs"
umount_if_mounted "${ALTROOT}/mnt/python"
umount_if_mounted "${ALTROOT}/mnt/modloop"
umount_if_mounted "${ALTROOT}/mnt/rootfs"
umount_if_mounted "${ALTROOT}/mnt/failsafe"

head "Démontage des datasets ZFS"
umount_if_mounted "${ALTROOT}/home"
umount_if_mounted "${ALTROOT}/tmp"
umount_if_mounted "${ALTROOT}/var/log"
umount_if_mounted "${ALTROOT}/var"
umount_if_mounted "${ALTROOT}/mnt/fast"

head "Démontage de boot_pool"
# boot_pool/images doit être démonté AVANT boot_pool (enfant ZFS — ordre strict)
if zfs list boot_pool/images >/dev/null 2>&1; then
    X zfs unmount boot_pool/images 2>/dev/null && ok "boot_pool/images démonté" || true
fi

# boot_pool est toujours monté sur $ZBM_BOOT (= /mnt/zbm/boot).
# En mode --chroot, ${ALTROOT}/boot peut aussi être valide.
_ZBM_BOOT_MP="${ZBM_BOOT:-/mnt/zbm/boot}"
umount_if_mounted "$_ZBM_BOOT_MP"
# Compatibilité : si l'ancienne convention /mnt/zbm-live était utilisée
umount_if_mounted "/mnt/zbm-live" 2>/dev/null || true  # compat ancien chemin
# Chroot : l'altroot/boot est aussi boot_pool
[[ "$ALTROOT" != "/" ]] && umount_if_mounted "${ALTROOT}/boot" || true

head "Export des pools"
for pool in data_pool fast_pool boot_pool; do
    if zpool list "$pool" >/dev/null 2>&1; then
        X zpool export "$pool" && ok "exporté : $pool" || warn "export échoué : $pool"
    else
        skip "$pool (non importé)"
    fi
done

echo ""
ok "Démontage terminé"
