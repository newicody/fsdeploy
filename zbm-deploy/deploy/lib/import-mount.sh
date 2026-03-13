#!/bin/bash
# =============================================================================
# lib/import-mount.sh
# Inspection / chroot — Monte les pools ZFS pour accéder à un système installé.
#
# USAGE PRINCIPAL : inspection post-installation, chroot de rescue, debug.
# NE PAS utiliser pour le DÉPLOIEMENT initial (deploy.sh gère boot_pool seul).
#
# ARCHITECTURE OVERLAY (invariant clé) :
#   Chaque système = lower (rootfs.sfs) + upper (fast_pool/overlay-<s>)
#   /var /tmp sont dans le lower et écrits dans l'upper. Aucun dataset séparé.
#   fast_pool/var-<s> / fast_pool/log-<s> / fast_pool/tmp-<s> n'existent PAS.
#
# USAGE :
#   bash lib/import-mount.sh [--system systeme1] [--altroot /mnt/zbm] [--chroot]
#
#   --system   : systeme1 | systeme2 | failsafe  (défaut : systeme1)
#   --altroot  : préfixe pour tous les mountpoints  (défaut : /mnt/zbm)
#   --chroot   : on est dans un chroot → altroot=/  (ignore --altroot)
#   --dry-run  : afficher les commandes sans les exécuter
#
# ORDRE DE MONTAGE :
#   1. boot_pool                → /mnt/zbm/boot        (legacy, explicite)
#   2. boot_pool/images         → /mnt/zbm/boot/images (dataset enfant)
#   3. fast_pool/overlay-<sys>  → <altroot>/mnt/fast   (upper OverlayFS)
#   4. data_pool/home           → <altroot>/home        (partagé)
#   5. rootfs.sfs               → <altroot>/mnt/rootfs  (squashfs RO)
#   6. modules.sfs              → <altroot>/mnt/modloop (squashfs RO)
#   7. python.sfs               → <altroot>/mnt/python  (squashfs RO)
#
# IDEMPOTENT : peut être relancé sans risque.
# =============================================================================

set -euo pipefail

# Source de vérité pour les points de montage
_MOUNTS_SH="$(dirname "${BASH_SOURCE[0]}")/mounts.sh"
[[ -f "$_MOUNTS_SH" ]] && source "$_MOUNTS_SH"


GREEN='\033[1;32m'; YELLOW='\033[1;33m'; RED='\033[1;31m'
CYAN='\033[1;36m'; BOLD='\033[1m'; DIM='\033[2m'; NC='\033[0m'

ok()    { echo -e "  ${GREEN}✅${NC} $*"; }
warn()  { echo -e "  ${YELLOW}⚠️ ${NC} $*"; }
err()   { echo -e "  ${RED}❌${NC} $*"; exit 1; }
info()  { echo -e "  ${CYAN}   $*${NC}"; }
skip()  { echo -e "  ${DIM}  ↷ $* (déjà fait)${NC}"; }
head()  { echo -e "\n${BOLD}── $* ──${NC}"; }

# =============================================================================
# PARSE DES ARGUMENTS
# =============================================================================
SYSTEM="systeme1"
ALTROOT="${ZBM_ALTROOT:-/mnt/zbm}"
DRY_RUN=0
CHROOT_MODE=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --system)    SYSTEM="$2";   shift 2 ;;
        --altroot)   ALTROOT="$2";  shift 2 ;;
        --chroot)    CHROOT_MODE=1; ALTROOT="/"; shift ;;
        --dry-run)   DRY_RUN=1;     shift ;;
        -h|--help)
            grep '^#' "$0" | head -60 | sed 's/^# \?//'
            exit 0 ;;
        *) err "Argument inconnu : $1" ;;
    esac
done

# Valider le système — liste lue depuis config.sh (source de vérité)
_CONF="$(dirname "$0")/../config.sh"
_VALID_SYSTEMS=("failsafe")
if [[ -f "$_CONF" ]]; then
    # Lecture des systèmes via sous-shell propre — sans quoting hell
    while IFS= read -r s; do
        [[ -n "$s" ]] && _VALID_SYSTEMS+=("$s")
    done < <(env CONF="$_CONF" bash -c 'source "$CONF" 2>/dev/null; printf "%s
" "${SYSTEMS[@]:-}"' 2>/dev/null || true)
fi

_found=0
for _s in "${_VALID_SYSTEMS[@]}"; do
    [[ "$_s" == "$SYSTEM" ]] && _found=1 && break
done
if [[ $_found -eq 0 ]]; then
    err "Système inconnu : $SYSTEM  (valeurs disponibles : ${_VALID_SYSTEMS[*]})"
fi
unset _CONF _raw _s _found

# Normaliser altroot
[[ "$ALTROOT" == "/" ]] || ALTROOT="${ALTROOT%/}"

# Wrapper pour dry-run
X() {
    if [[ $DRY_RUN -eq 1 ]]; then
        echo -e "  ${DIM}[dry]${NC} $*"
    else
        "$@"
    fi
}

# =============================================================================
# AFFICHAGE DE LA CONFIGURATION
# =============================================================================
echo -e "\n${CYAN}${BOLD}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║   ZBM — Import & montage                                    ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo "  Système  : ${BOLD}$SYSTEM${NC}"
echo "  Altroot  : ${BOLD}$ALTROOT${NC}"
[[ $CHROOT_MODE -eq 1 ]] && echo "  Mode     : chroot (altroot=/)"
[[ $DRY_RUN     -eq 1 ]] && echo -e "  ${YELLOW}Mode dry-run — aucune modification${NC}"
echo ""

# Architecture overlay : UN seul dataset par système (overlay = upper OverlayFS)
# Aucun dataset var/log/tmp — ils vivent dans le lower (rootfs.sfs) + upper (overlay).
DS_OVERLAY="fast_pool/overlay-${SYSTEM}"
if [[ "$SYSTEM" == "failsafe" ]]; then
    DS_HOME=""      # failsafe : pas d'accès /home
else
    DS_HOME="data_pool/home"
fi

# =============================================================================
# 1. MODULES KERNEL
# =============================================================================
head "Modules kernel"

for mod in zfs overlay squashfs loop; do
    modprobe "$mod" 2>/dev/null && ok "$mod" || skip "$mod (builtin ou déjà chargé)"
done

# Attendre udev
udevadm settle 2>/dev/null || true

# =============================================================================
# 2. IMPORT DES POOLS AVEC -R <altroot>
# =============================================================================
head "Import des pools ZFS  (altroot=${ALTROOT})"

# Créer l'altroot si nécessaire
[[ "$ALTROOT" != "/" ]] && X mkdir -p "$ALTROOT"

import_pool() {
    local pool="$1" required="${2:-0}" skip_altroot="${3:-0}"
    # skip_altroot=1 pour boot_pool : TOUJOURS monté via "mount -t zfs" explicite,
    # l'altroot ZFS est irrelevant → ne jamais bloquer sur un mismatch.

    if zpool list "$pool" >/dev/null 2>&1; then
        HEALTH=$(zpool list -H -o health "$pool" 2>/dev/null || echo "?")

        if [[ "$skip_altroot" -eq 1 ]]; then
            # boot_pool : peu importe l'altroot stocké, on monte explicitement
            skip "$pool  [$HEALTH]  (altroot ignoré — montage explicite)"
            return 0
        fi

        # fast_pool / data_pool : altroot doit correspondre pour "zfs mount"
        CUR_ALT=$(zpool get -H -o value altroot "$pool" 2>/dev/null || echo "")
        [[ "$CUR_ALT" == "-" ]] && CUR_ALT=""   # ZFS stocke "-" quand aucun altroot
        if [[ "$CUR_ALT" == "$ALTROOT" ]] || [[ "$ALTROOT" == "/" && -z "$CUR_ALT" ]]; then
            skip "$pool  [$HEALTH]  altroot OK"
            return 0
        fi

        # Altroot mismatch : essayer export + reimport
        warn "$pool importé avec altroot='${CUR_ALT:-/}' ≠ '${ALTROOT}' — export + reimport"
        if X zpool export "$pool" 2>/dev/null; then
            ok "$pool exporté — reimport en cours..."
            # Continuer vers l'import ci-dessous
        else
            warn "$pool : export impossible (datasets montés ? synchro en cours ?)"
            if [[ $required -eq 1 ]]; then
                err "$pool : altroot incompatible et export impossible.
  Démontez les datasets puis : zpool export $pool
  Ou relancez avec : --altroot ${CUR_ALT:-/}"
            fi
            return 1
        fi
    fi

    # Construire la commande d'import
    local IMPORT_CMD=(zpool import)
    # boot_pool (skip_altroot=1) : pas de -R, monté toujours via mount -t zfs explicite
    [[ "$skip_altroot" -eq 0 && "$ALTROOT" != "/" ]] && IMPORT_CMD+=(-R "$ALTROOT")
    IMPORT_CMD+=(-N "$pool")   # -N : ne pas monter les datasets automatiquement

    if X "${IMPORT_CMD[@]}" 2>/dev/null; then
        ok "$pool importé${skip_altroot:+  (sans -R — montage explicite)}"
        return 0
    fi

    # Forcer si le pool vient d'un autre système (dirty import)
    IMPORT_CMD+=(-f)
    if X "${IMPORT_CMD[@]}" 2>/dev/null; then
        warn "$pool importé en mode forcé (-f)"
        return 0
    fi

    if [[ $required -eq 1 ]]; then
        err "$pool introuvable — vérifiez les disques"
    fi
    warn "$pool non trouvé — ignoré"
    return 1
}

# boot_pool : skip_altroot=1 — monté toujours via "mount -t zfs" explicite
# fast_pool / data_pool : altroot=/mnt/zbm nécessaire pour "zfs mount"
BOOT_OK=0;  import_pool boot_pool  1 1 && BOOT_OK=1
FAST_OK=0;  import_pool fast_pool  1 0 && FAST_OK=1
DATA_OK=0;  import_pool data_pool  0 0 && DATA_OK=1

# =============================================================================
# 3. MONTAGE DES DATASETS ZFS
#    On monte manuellement dans l'ordre (parent avant enfant).
#    -R a fixé l'altroot à l'import, zfs mount respecte ce préfixe.
# =============================================================================
head "Montage des datasets ZFS"

mount_ds() {
    local ds="$1"
    # Calculer le chemin réel = altroot + mountpoint_zfs
    local zmp
    zmp=$(zfs get -H -o value mountpoint "$ds" 2>/dev/null || echo "")
    [[ -z "$zmp" || "$zmp" == "none" || "$zmp" == "legacy" ]] && {
        skip "$ds (mountpoint=none/legacy)"
        return 0
    }

    local real_mp
    if [[ "$ALTROOT" == "/" ]]; then
        real_mp="$zmp"
    else
        real_mp="${ALTROOT}${zmp}"
    fi

    if mountpoint -q "$real_mp" 2>/dev/null; then
        skip "$ds → $real_mp"
        return 0
    fi

    if ! zfs list "$ds" >/dev/null 2>&1; then
        warn "$ds : dataset absent — ignoré"
        return 1
    fi

    X mkdir -p "$real_mp"
    if X zfs mount "$ds" 2>/dev/null; then
        ok "$ds → $real_mp"
    else
        # Fallback : mount -t zfs avec l'option -o mountpoint
        X mount -t zfs -o mountpoint="$real_mp" "$ds" "$real_mp" 2>/dev/null \
            && ok "$ds → $real_mp  (fallback mount -t zfs)" \
            || warn "$ds : montage échoué"
    fi
}

# boot_pool — mountpoint=legacy (géré par ZBM) : montage EXPLICITE requis
# "zfs mount boot_pool" ne fonctionne pas sur mountpoint=legacy → mount -t zfs
# boot_pool a mountpoint=legacy → montage explicite sur $ZBM_BOOT (= /mnt/zbm/boot).
# Cohérent avec l'altroot /mnt/zbm : toutes les données du système sous /mnt/zbm/.
# /boot du live CD est occupé par Debian — on ne l'utilise jamais.
# Si BOOT a déjà été exporté par deploy.sh (et est monté), on le réutilise.
if [[ -n "${BOOT:-}" ]] && mountpoint -q "${BOOT}" 2>/dev/null; then
    : # BOOT déjà valide — réutiliser
elif zfs mount 2>/dev/null | awk '{print $1}' | grep -q "^boot_pool$"; then
    BOOT=$(zfs mount 2>/dev/null | awk '$1=="boot_pool"{print $2}' | head -1)
else
    BOOT="${ZBM_BOOT:-/mnt/zbm/boot}"
fi

_zmp_boot=$(zfs get -H -o value mountpoint boot_pool 2>/dev/null || echo "")
if [[ "$_zmp_boot" == "legacy" ]]; then
    if mountpoint -q "$BOOT" 2>/dev/null; then
        skip "boot_pool → $BOOT  (déjà monté)"
    else
        X mkdir -p "$BOOT"
        if X mount -t zfs boot_pool "$BOOT" 2>/dev/null; then
            ok "boot_pool → $BOOT  (legacy mount)"
        else
            warn "boot_pool : montage échoué sur $BOOT"
        fi
    fi
else
    # mountpoint=/boot ou autre : laisser mount_ds gérer
    mount_ds boot_pool
fi

# boot_pool/images — dataset enfant ZFS normal de boot_pool (mountpoint hérité)
# "zfs mount boot_pool/images" le monte automatiquement sur $BOOT/images
if [[ $BOOT_OK -eq 1 ]]; then
    if zfs list boot_pool/images >/dev/null 2>&1; then
        if mountpoint -q "$BOOT/images" 2>/dev/null; then
            skip "boot_pool/images → $BOOT/images  (déjà monté)"
        else
            X mkdir -p "$BOOT/images"
            if X zfs mount boot_pool/images 2>/dev/null; then
                ok "boot_pool/images → $BOOT/images"
            else
                warn "boot_pool/images : zfs mount échoué"
            fi
        fi
    else
        warn "boot_pool/images : dataset absent — lancez lib/datasets-check.sh --initial"
    fi
fi

# fast_pool — overlay d'abord (parent des mounts overlay)

if [[ $FAST_OK -eq 1 ]]; then
    # Overlay : montage pour inspection (chroot/rescue).
    # En mode déploiement normal, l'overlay est monté par initramfs au boot.
    MNT_FAST="${ALTROOT%/}/mnt/fast"
    [[ "$ALTROOT" == "/" ]] && MNT_FAST="/mnt/fast"

    if zfs list "$DS_OVERLAY" >/dev/null 2>&1; then
        if mountpoint -q "$MNT_FAST" 2>/dev/null; then
            skip "$DS_OVERLAY → $MNT_FAST"
        else
            X mkdir -p "$MNT_FAST"
            if X mount -t zfs "$DS_OVERLAY" "$MNT_FAST" 2>/dev/null; then
                X mkdir -p "$MNT_FAST/upper" "$MNT_FAST/.work"
                ok "$DS_OVERLAY → $MNT_FAST"
            else
                warn "$DS_OVERLAY : montage échoué (dataset vide ou non initialisé ?)"
            fi
        fi
    else
        warn "$DS_OVERLAY absent — créez-le via datasets-check.sh --system $SYSTEM"
    fi

    # /var /tmp /run = dans le lower (rootfs.sfs) + upper (overlay) — pas de datasets ZFS
    info "Architecture overlay : /var /tmp gérés par fast_pool/overlay-${SYSTEM}/upper"
    info "Les écritures /var et /tmp vont dans $DS_OVERLAY/upper/"
fi

# data_pool
if [[ $DATA_OK -eq 1 ]]; then
    [[ -n "$DS_HOME" ]] && mount_ds "$DS_HOME" || skip "home (non défini pour $SYSTEM)"
fi

# =============================================================================
# 4. MONTAGE DES IMAGES SQUASHFS
# =============================================================================
head "Montage des images squashfs"

# Points de montage relatifs à l'altroot
MNT_ROOTFS="${ALTROOT%/}/mnt/rootfs"
MNT_MODLOOP="${ALTROOT%/}/mnt/modloop"
MNT_PYTHON="${ALTROOT%/}/mnt/python"
[[ "$ALTROOT" == "/" ]] && {
    MNT_ROOTFS="/mnt/rootfs"
    MNT_MODLOOP="/mnt/modloop"
    MNT_PYTHON="/mnt/python"
}

mount_sfs() {
    local label="$1" src="$2" dst="$3"

    if [[ -z "$src" ]] || [[ ! -f "$src" ]]; then
        warn "$label : fichier absent${src:+  ($src)}"
        return 1
    fi
    if mountpoint -q "$dst" 2>/dev/null; then
        skip "$label → $dst"
        return 0
    fi
    X mkdir -p "$dst"
    if X mount -t squashfs -o loop,ro "$src" "$dst" 2>/dev/null; then
        SIZE=$(df -h "$dst" 2>/dev/null | tail -1 | awk '{print $2}' || echo "?")
        ok "$label → $dst  (${SIZE})"
    else
        warn "$label : montage squashfs échoué ($src)"
        return 1
    fi
}

# Résoudre les sources squashfs depuis les symlinks /boot ou les fichiers directs
resolve_sfs() {
    local link_name="$1" glob_rel="$2"
    # Les symlinks actifs sont dans $BOOT/boot/ (là où ZBM cherche vmlinuz)
    local link="${BOOT}/boot/${link_name}"
    # Symlink actif dans $BOOT/boot/ ?
    if [[ -L "$link" ]] && [[ -f "$link" ]]; then
        readlink -f "$link"; return
    fi
    # Glob dans $BOOT/images/
    local found
    found=$(ls "${BOOT}/${glob_rel}" 2>/dev/null | sort | tail -1 || true)
    echo "${found:-}"
}

# rootfs — correspond au système sélectionné
# Le symlink rootfs.sfs pointe vers le rootfs du système actif.
# Si le système demandé est différent du système actif, on cherche son rootfs direct.
ROOTFS_SFS=""
case "$SYSTEM" in
    failsafe)
        ROOTFS_SFS=$(ls "${BOOT}/images/failsafe/rootfs-failsafe.sfs" 2>/dev/null || true)
        [[ -z "$ROOTFS_SFS" ]] && \
            ROOTFS_SFS=$(ls "${BOOT}/images/rootfs/"*failsafe*.sfs 2>/dev/null | head -1 || true)
        ;;
    *)
        # Convention : rootfs-<system>-<label>-<date>.sfs — prendre le plus récent
        ROOTFS_SFS=$(ls "${BOOT}/images/rootfs/rootfs-${SYSTEM}-"*.sfs 2>/dev/null \
            | sort | tail -1 || true)
        [[ -z "$ROOTFS_SFS" ]] && \
            ROOTFS_SFS=$(resolve_sfs "rootfs.sfs" "images/rootfs/*.sfs")
        ;;
esac

MODULES_SFS=$(resolve_sfs "modules.sfs" "images/modules/modules*.sfs")
PYTHON_SFS=$(ls "${BOOT}/images/startup/"python*.sfs 2>/dev/null | head -1 || true)

mount_sfs "rootfs [${SYSTEM}]" "$ROOTFS_SFS"  "$MNT_ROOTFS"
mount_sfs "modules"            "$MODULES_SFS" "$MNT_MODLOOP"
mount_sfs "python"             "$PYTHON_SFS"  "$MNT_PYTHON"

# =============================================================================
# 5. RÉCAPITULATIF
# =============================================================================
head "Récapitulatif"

echo ""
echo -e "  ${BOLD}Système monté : ${CYAN}${SYSTEM}${NC}  (altroot=${ALTROOT})"
echo ""

# Pools
echo -e "  ${BOLD}Pools :${NC}"
zpool list 2>/dev/null | awk 'NR==1{printf "    %s\n",$0} NR>1{printf "    %s\n",$0}' || true

# Datasets montés filtrés sur nos pools
echo ""
echo -e "  ${BOLD}Datasets montés :${NC}"
{
    zfs mount 2>/dev/null | grep -E "^(boot_pool|fast_pool|data_pool)" || true
} | while read -r ds mp; do
    printf "    %-38s → %s\n" "$ds" "$mp"
done

# Squashfs
echo ""
echo -e "  ${BOLD}Squashfs montés :${NC}"
mount 2>/dev/null | grep squashfs | \
    awk '{printf "    %-45s → %s\n", $1, $3}' || echo "    aucun"

# Arbre du montage cible
echo ""
echo -e "  ${BOLD}Arbre des montages sous ${ALTROOT} :${NC}"
findmnt --real -o TARGET,SOURCE,FSTYPE,SIZE \
    --target "$ALTROOT" 2>/dev/null | head -30 | sed 's/^/    /' || \
findmnt -o TARGET,SOURCE,FSTYPE 2>/dev/null | grep "^${ALTROOT}" | sed 's/^/    /' || true

echo ""
ok "Prêt — les données de '${SYSTEM}' sont accessibles sous ${ALTROOT}"
echo ""
echo -e "  ${DIM}Pour démonter proprement : bash lib/umount.sh --altroot ${ALTROOT}${NC}"
echo ""
