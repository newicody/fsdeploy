#!/bin/bash
# =============================================================================
# update-failsafe-links.sh — Crée/rafraîchit les symlinks failsafe dans /boot
# Prérequis : create-failsafe.sh doit avoir été exécuté
#
# IDEMPOTENT — relançable sans risque.
# Ce script fait UNE SEULE CHOSE : créer les 4 symlinks *.failsafe
# en pointant vers le dernier failsafe disponible dans /boot/images/failsafe/
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
for candidate in "$SCRIPT_DIR/lib/naming.sh" "$SCRIPT_DIR/naming.sh"; do
    [[ -f "$candidate" ]] && { source "$candidate"; break; }
done
type zbm_stem &>/dev/null || { echo "naming.sh introuvable"; exit 1; }

RED='\033[1;31m'; GREEN='\033[1;32m'; YELLOW='\033[1;33m'; BOLD='\033[1m'; NC='\033[0m'
ok()   { echo -e "  ${GREEN}✅ $*${NC}"; }
err()  { echo -e "  ${RED}❌ $*${NC}"; exit 1; }
warn() { echo -e "  ${YELLOW}⚠️  $*${NC}"; }

[[ $EUID -ne 0 ]] && err "Root requis"

_MOUNTED_BOOT=0
_cleanup_boot() {
    [[ "${_MOUNTED_BOOT:-0}" -eq 1 ]] && { umount "${BOOT:-}" 2>/dev/null; rmdir "${BOOT:-}" 2>/dev/null; } || true
}
trap _cleanup_boot EXIT
BOOT=$(zfs mount 2>/dev/null | awk '$1=="boot_pool"{print $2}' || true)
if [[ -z "$BOOT" ]]; then
    zpool import -N boot_pool 2>/dev/null || true
    BOOT="/mnt/boot-deploy-$$"
    mkdir -p "$BOOT"
    mount -t zfs boot_pool "$BOOT" 2>/dev/null \
        || err "boot_pool non montable -- lancez d'abord import-mount.sh"
    _MOUNTED_BOOT=1
fi
export BOOT  # Propagé aux sous-shells ($(zbm_dir ...) etc.)
FS_DIR="$(zbm_dir failsafe)"

[[ -d "$FS_DIR" ]] || err "Répertoire failsafe absent. Lancez d'abord create-failsafe.sh"

# =============================================================================
# TROUVER LE FAILSAFE LE PLUS RÉCENT
# =============================================================================
echo "  Recherche du failsafe le plus récent..."

FS_LABEL="" FS_DATE=""
for f in "$FS_DIR"/kernel-failsafe-*; do
    [[ -f "$f" ]] || continue
    eval "$(zbm_parse "$f")" || continue
    # Garder le plus récent
    if [[ -z "$FS_DATE" ]] || [[ "$ZBM_DATE" > "$FS_DATE" ]]; then
        FS_LABEL="$ZBM_LABEL"
        FS_DATE="$ZBM_DATE"
    fi
done

[[ -n "$FS_DATE" ]] || err "Aucun kernel failsafe trouvé dans $FS_DIR"
echo "  Failsafe retenu : failsafe/${FS_LABEL}/${FS_DATE}"

# Vérifier que l'ensemble failsafe est complet
for type in kernel initramfs modules rootfs; do
    f=$(zbm_path "$type" failsafe "$FS_LABEL" "$FS_DATE")
    [[ -f "$f" ]] || err "Fichier manquant : $(basename "$f")"
    ok "$(basename "$f")"
done

# =============================================================================
# SYMLINKS
# =============================================================================
echo ""
# Les symlinks failsafe sont dans $BOOT/boot/ (ZBM cherche <BE>/boot/vmlinuz.failsafe)
BOOT_LINKS_DIR="$BOOT/boot"
mkdir -p "$BOOT_LINKS_DIR"
echo "  Création des symlinks failsafe dans $BOOT_LINKS_DIR/..."

FAIL=0
while IFS='|' read -r link_name target_rel; do
    lp="$BOOT_LINKS_DIR/$link_name"
    full_target="$BOOT/$target_rel"
    # Chemin relatif depuis $BOOT/boot/
    rel=$(realpath --relative-to="$BOOT_LINKS_DIR" "$full_target" 2>/dev/null || echo "$target_rel")

    if [[ ! -e "$full_target" ]]; then
        err "$link_name : cible introuvable → $full_target"
        FAIL=$((FAIL+1))
        continue
    fi

    if [[ -L "$lp" ]]; then
        current=$(readlink "$lp")
        if [[ "$current" == "$rel" ]]; then
            ok "$link_name  (déjà correct)"
            continue
        else
            warn "$link_name  (mis à jour : $current → $rel)"
        fi
    elif [[ -e "$lp" ]]; then
        err "$link_name existe mais n'est pas un symlink — abandon"
        exit 1
    fi

    ln -sf "$rel" "$lp"
    ok "boot/$link_name → $rel"
done < <(zbm_failsafe_links "$FS_LABEL" "$FS_DATE")

[[ $FAIL -gt 0 ]] && { echo -e "\n${RED}$FAIL lien(s) cassé(s)${NC}"; exit 1; }

# =============================================================================
# RÉSUMÉ
# =============================================================================
echo ""
echo -e "${GREEN}${BOLD}╔══════════════════════════════════════════════════════════════╗"
echo            "║   ✅ SYMLINKS FAILSAFE CRÉÉS                                 ║"
echo -e         "╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "  Symlinks failsafe :"
for link in vmlinuz.failsafe initrd.failsafe.img modules.failsafe.sfs rootfs.failsafe.sfs; do
    lp="$BOOT/boot/$link"
    [[ -L "$lp" ]] \
        && printf "    %-32s → %s\n" "$link" "$(readlink "$lp")" \
        || printf "    %-32s   [manquant]\n" "$link"
done
echo ""
echo "  Symlinks actifs (gérés par la TUI) :"
for link in vmlinuz initrd.img modules.sfs rootfs.sfs; do
    lp="$BOOT/boot/$link"
    [[ -L "$lp" ]] \
        && printf "    %-32s → %s\n" "$link" "$(readlink "$lp")" \
        || printf "    %-32s   [non défini]\n" "$link"
done
echo ""
