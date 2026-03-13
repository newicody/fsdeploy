#!/bin/bash
# lib/09-failsafe.sh — Installation du failsafe depuis le contexte de déploiement
# Appelle create-failsafe.sh puis update-failsafe-links.sh (symlinks)
# Sourcé depuis deploy.sh avec config.sh déjà chargé

set -euo pipefail

# naming.sh fournit zbm_locate_boot(), zbm_cleanup_boot() et les fonctions de nommage
# Sourcé par deploy.sh OU directement si lancé seul
if [[ -z "$(type -t zbm_locate_boot 2>/dev/null)" ]]; then
    _NM="$(dirname "$0")/naming.sh"
    [[ -f "$_NM" ]] && source "$_NM" \
        || { echo "ERREUR: naming.sh introuvable — lancer depuis deploy.sh"; exit 1; }
fi

GREEN='\033[1;32m'; YELLOW='\033[1;33m'; RED='\033[1;31m'; CYAN='\033[1;36m'; NC='\033[0m'
ok()   { echo -e "  ${GREEN}OK $*${NC}"; }
warn() { echo -e "  ${YELLOW}WARN $*${NC}"; }
err()  { echo -e "  ${RED}ERR $*${NC}"; exit 1; }
info() { echo -e "  ${CYAN}   $*${NC}"; }

DEPLOY_ROOT="$(dirname "$(dirname "$0")")"
# Localisation de boot_pool — utilise zbm_locate_boot() de naming.sh
# Sur Debian live /boot est occupé → boot_pool monté sur ${ZBM_BOOT:-/mnt/zbm/boot}
_MOUNTED_BOOT=0  # rétrocompat
_cleanup_boot() { zbm_cleanup_boot; }
trap _cleanup_boot EXIT
zbm_locate_boot || err "boot_pool introuvable — vérifiez les pools ZFS"
info "boot_pool -> $BOOT"

FAILSAFE_DIR="$BOOT/images/failsafe"

# Rootfs source : utiliser le premier système défini dans config.sh, ou systeme1
# config.sh peut avoir été chargé par deploy.sh ou est disponible à côté
CONF_FILE="$(dirname "$DEPLOY_ROOT")/deploy/config.sh"
_FS_SYSTEM="systeme1"
_FS_LABEL="gentoo"
if [[ -f "$CONF_FILE" ]]; then
    _FS_SYSTEM=$(env CONF="$CONF_FILE" bash -c 'source "$CONF" 2>/dev/null; echo "${SYSTEMS[0]:-systeme1}"')
    _FS_LABEL=$(env CONF="$CONF_FILE" bash -c 'source "$CONF" 2>/dev/null; echo "${ROOTFS_LABEL:-gentoo}"')
fi
ROOTFS_SRC="$BOOT/images/rootfs"
# Chercher le rootfs le plus récent pour ce système
ROOTFS_SRC_FILE=$(ls "$ROOTFS_SRC/rootfs-${_FS_SYSTEM}-"*.sfs 2>/dev/null | sort | tail -1 || true)
if [[ -z "$ROOTFS_SRC_FILE" ]]; then
    # Fallback : n'importe quel rootfs disponible
    ROOTFS_SRC_FILE=$(ls "$ROOTFS_SRC/"rootfs-*.sfs 2>/dev/null | sort | tail -1 || true)
fi
[[ -n "$ROOTFS_SRC_FILE" ]] || err "Aucun rootfs dans $ROOTFS_SRC (lancez 04-rootfs.sh)"
info "Rootfs source : $ROOTFS_SRC_FILE"

# =============================================================================
# Appel de create-failsafe.sh
# =============================================================================
FS_SCRIPT="$DEPLOY_ROOT/create-failsafe.sh"
[[ -f "$FS_SCRIPT" ]] || err "Script manquant : $FS_SCRIPT"

echo "  Création des images failsafe..."
# create-failsafe.sh attend : $1=SRC_SYSTEM  $2=LABEL  [$3=date]
bash "$FS_SCRIPT" "$_FS_SYSTEM" "$_FS_LABEL"

# =============================================================================
# Appel de update-failsafe-links.sh (symlinks)
# =============================================================================
LINK_SCRIPT="$DEPLOY_ROOT/update-failsafe-links.sh"
[[ -f "$LINK_SCRIPT" ]] || err "Script manquant : $LINK_SCRIPT"

echo "  Création des symlinks failsafe..."
bash "$LINK_SCRIPT"

ok "Failsafe installé et symlinks créés"
