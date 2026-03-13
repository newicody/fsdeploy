#!/bin/bash
# =============================================================================
# lib/rootfs.sh — Installation d'un rootfs squashfs dans /boot/images/rootfs/
#
# RÔLE UNIQUE : copier un fichier .sfs dans la bonne destination avec
#               le bon nom selon la convention, et générer le .meta.
#
# ⚠️  CE SCRIPT NE TOUCHE PAS AUX KERNELS NI AUX MODULES.
#    Un rootfs est une image squashfs du système de fichiers racine.
#    Les kernels et modules sont gérés INDÉPENDAMMENT par kernel.sh.
#
# Variables :
#   SYSTEM        systeme1 | systeme2   (demandé si absent)
#   ROOTFS_LABEL  ex: gentoo            (demandé si absent)
#   IMAGE_DATE    YYYYMMDD              (défaut : aujourd'hui)
#   ROOTFS_SRC    chemin source .sfs    (défaut : auto-détection)
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/naming.sh"

GREEN='\033[1;32m'; YELLOW='\033[1;33m'; RED='\033[1;31m'; BOLD='\033[1m'; NC='\033[0m'
ok()   { echo -e "  ${GREEN}✅ $*${NC}"; }
warn() { echo -e "  ${YELLOW}⚠️  $*${NC}"; }
err()  { echo -e "  ${RED}❌ $*${NC}"; exit 1; }

# Localisation de boot_pool — utilise zbm_locate_boot() de naming.sh
# Sur Debian live /boot est occupé → boot_pool monté sur ${ZBM_BOOT:-/mnt/zbm/boot}
_MOUNTED_BOOT=0  # rétrocompat
_cleanup_boot() { zbm_cleanup_boot; }
trap _cleanup_boot EXIT
zbm_locate_boot || err "boot_pool introuvable — vérifiez les pools ZFS"
TODAY="${IMAGE_DATE:-$(date +%Y%m%d)}"

# Paramètre SYSTEM : lu depuis config.sh SYSTEMS ou saisi
CONF="$(dirname "$SCRIPT_DIR")/config.sh"
[[ -f "$CONF" ]] && source "$CONF" || true

if [[ -z "${SYSTEM:-}" ]]; then
    # Lire les systèmes depuis config.sh
    declare -a _SYS_LIST=()
    _raw=$(env CONF="$CONF" bash -c 'source "$CONF" 2>/dev/null; printf "%s\n" "${SYSTEMS[@]:-}"' 2>/dev/null || true)
    while IFS= read -r s; do [[ -n "$s" ]] && _SYS_LIST+=("$s"); done <<< "$_raw"

    if [[ ${#_SYS_LIST[@]} -eq 1 ]]; then
        SYSTEM="${_SYS_LIST[0]}"
        echo "  Systeme : $SYSTEM (depuis config.sh)"
    elif [[ ${#_SYS_LIST[@]} -gt 1 ]]; then
        echo ""
        echo "  Systemes disponibles (depuis config.sh SYSTEMS) :"
        for i in "${!_SYS_LIST[@]}"; do
            echo "    $((i+1))) ${_SYS_LIST[$i]}"
        done
        echo -n "  Choisir [1-${#_SYS_LIST[@]}] : "
        read -r _IDX
        SYSTEM="${_SYS_LIST[$((_IDX-1))]}"
    else
        echo -n "  Nom du systeme (ex: systeme1) : "
        read -r SYSTEM
    fi
fi
[[ -n "${SYSTEM:-}" ]] || err "SYSTEM requis"

if [[ -z "${ROOTFS_LABEL:-}" ]]; then
    echo -n "  Label rootfs (ex: gentoo, arch) : "
    read -r ROOTFS_LABEL
fi
[[ -n "$ROOTFS_LABEL" ]] || err "ROOTFS_LABEL requis"

ROOTFS_DST=$(zbm_path rootfs "$SYSTEM" "$ROOTFS_LABEL" "$TODAY")
mkdir -p "$(zbm_dir rootfs)"

echo -e "\n  ${BOLD}Paramètres${NC}"
echo "  Système   : $SYSTEM"
echo "  Label     : $ROOTFS_LABEL"
echo "  Date      : $TODAY"
echo "  Cible     : $(basename "$ROOTFS_DST")"
echo ""
echo -e "  ${YELLOW}⚠️  Le rootfs NE DOIT PAS contenir kernel ni modules.${NC}"
echo -e "  ${YELLOW}   Gérez-les séparément avec kernel.sh${NC}"

# Protection : ne pas écraser sans confirmation
if [[ -f "$ROOTFS_DST" ]]; then
    echo ""
    warn "$(basename "$ROOTFS_DST") existe déjà"
    echo -n "  Écraser ? [o/N] : "
    read -r CONFIRM
    [[ "$CONFIRM" =~ ^[Oo]$ ]] || { ok "Annulé — fichier existant conservé"; exit 0; }
fi

# =============================================================================
# 1. LOCALISER LE ROOTFS SOURCE
# =============================================================================
echo "  Localisation du rootfs source..."
SFS_FOUND=""

if [[ "${ROOTFS_SRC:-auto}" == "auto" ]]; then
    SEARCH_PATHS=(
        "$BOOT/images/rootfs/rootfs-${SYSTEM}-${ROOTFS_LABEL}-"*".sfs"
        "/mnt/usb/rootfs.sfs"
        "/run/live/medium/rootfs.sfs"
    )
    while IFS= read -r line; do
        MP=$(echo "$line" | awk '{print $2}')
        for p in "rootfs.sfs" "${SYSTEM}-rootfs.sfs" "${ROOTFS_LABEL}.sfs"; do
            [[ -f "$MP/$p" ]] && SEARCH_PATHS+=("$MP/$p")
        done
    done < /proc/mounts

    for pattern in "${SEARCH_PATHS[@]}"; do
        for f in $pattern; do
            [[ -f "$f" ]] && { SFS_FOUND="$f"; break 2; }
        done
    done

    if [[ -z "$SFS_FOUND" ]]; then
        echo "  Rootfs non trouvé automatiquement."
        echo -n "  Chemin vers le .sfs source : "
        read -r SFS_FOUND
        [[ -f "$SFS_FOUND" ]] || err "Fichier introuvable : $SFS_FOUND"
    fi
else
    SFS_FOUND="$ROOTFS_SRC"
    [[ -f "$SFS_FOUND" ]] || err "Fichier introuvable : $SFS_FOUND"
fi

file "$SFS_FOUND" | grep -qi "squashfs" || warn "Avertissement : pas un squashfs valide"
ok "Source : $SFS_FOUND  ($(du -sh "$SFS_FOUND" | cut -f1))"

# =============================================================================
# 2. VÉRIFIER QUE LE ROOTFS NE CONTIENT PAS DE KERNEL OU MODULES
#    (avertissement uniquement — on copie quand même mais on ne les extrait pas)
# =============================================================================
echo "  Inspection du rootfs..."
TMP_MNT=$(mktemp -d)
mount -t squashfs -o loop,ro "$SFS_FOUND" "$TMP_MNT" 2>/dev/null || true

if [[ -d "$TMP_MNT/boot" ]]; then
    KERNEL_COUNT=$(find "$TMP_MNT/boot" -name "vmlinuz*" -o -name "kernel-*" 2>/dev/null | wc -l)
    if [[ $KERNEL_COUNT -gt 0 ]]; then
        warn "Le rootfs contient $KERNEL_COUNT fichier(s) kernel dans /boot"
        warn "Ils seront IGNORÉS — utilisez kernel.sh pour gérer les kernels"
    fi
fi
if [[ -d "$TMP_MNT/lib/modules" ]]; then
    MOD_COUNT=$(find "$TMP_MNT/lib/modules" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l)
    if [[ $MOD_COUNT -gt 0 ]]; then
        warn "Le rootfs contient $MOD_COUNT répertoire(s) de modules dans /lib/modules"
        warn "Ils seront IGNORÉS — utilisez kernel.sh pour générer modules-*.sfs"
    fi
fi

umount "$TMP_MNT" 2>/dev/null || true
rmdir "$TMP_MNT" 2>/dev/null || true

# =============================================================================
# 3. COPIER LE ROOTFS
# =============================================================================
if [[ "$SFS_FOUND" -ef "$ROOTFS_DST" ]]; then
    ok "Rootfs déjà en place (même fichier)"
else
    echo -n "  Copie rootfs..."
    cp --sparse=always "$SFS_FOUND" "$ROOTFS_DST"
    echo " OK"
    MD5_SRC=$(md5sum "$SFS_FOUND"  | awk '{print $1}')
    MD5_DST=$(md5sum "$ROOTFS_DST" | awk '{print $1}')
    [[ "$MD5_SRC" == "$MD5_DST" ]] || err "MD5 incorrect — copie corrompue, fichier supprimé"
fi
chmod 444 "$ROOTFS_DST"
ok "$(basename "$ROOTFS_DST")  ($(du -sh "$ROOTFS_DST" | cut -f1))"

# =============================================================================
# 4. SIDECAR .META
# =============================================================================
zbm_write_meta "$ROOTFS_DST" "builder=rootfs.sh"

# =============================================================================
# 5. RÉSUMÉ
# =============================================================================
echo ""
echo "  Rootfs disponibles :"
zbm_list_rootfs | while read -r sys lbl dt; do
    local_path=$(zbm_path rootfs "$sys" "$lbl" "$dt")
    sz=$(du -sh "$local_path" 2>/dev/null | cut -f1 || echo "?")
    printf "    rootfs-%-10s %-16s %s  (%s)\n" "$sys" "$lbl" "$dt" "$sz"
done
echo ""
echo -e "  ${YELLOW}Prochaine étape : bash lib/kernel.sh${NC}"
echo "  Ensuite créez un preset avec : bash lib/presets.sh"
