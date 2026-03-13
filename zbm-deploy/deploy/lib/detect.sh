#!/bin/bash
# =============================================================================
# lib/detect.sh -- Detection de l'environnement et ecriture de config.sh
#
# Detecte :
#   - NVMe presents (NVME_A = boot_pool, NVME_B = fast_pool)
#   - Partition EFI : toutes les partitions vfat ayant un rep EFI/ ou efi/
#     -> liste avec choix + default sur la premiere trouvee
#   - Partition boot_pool : partition ZFS sur NVME_A hors EFI
#   - Pools ZFS importables
#   - Images existantes dans boot_pool (kernels, initramfs, modules, rootfs)
#   - Systemes existants (datasets fast_pool/var-*)
#
# Ecrit : deploy/config.sh (pure ASCII, aucun caractere UTF-8)
# Preserve : SYSTEMS, KERNEL_LABEL, KERNEL_VER, INIT_TYPE,
#            STREAM_KEY, ROOTFS_LABEL, ROOTFS_SRC, reseau, stream
# =============================================================================

set -euo pipefail

# Source de vérité pour les points de montage
_MOUNTS_SH="$(dirname "${BASH_SOURCE[0]}")/mounts.sh"
[[ -f "$_MOUNTS_SH" ]] && source "$_MOUNTS_SH"


SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/naming.sh" 2>/dev/null || true

GREEN='\033[1;32m'; YELLOW='\033[1;33m'; RED='\033[1;31m'
CYAN='\033[1;36m'; BOLD='\033[1m'; NC='\033[0m'

ok()   { echo -e "  ${GREEN}OK${NC} $*"; }
warn() { echo -e "  ${YELLOW}WARN${NC} $*"; }
err()  { echo -e "  ${RED}ERR${NC} $*"; exit 1; }
info() { echo -e "  ${CYAN}    $*${NC}"; }
sep()  { echo -e "\n${BOLD}-- $* --${NC}"; }

CONF_FILE="$(dirname "$SCRIPT_DIR")/config.sh"

# =============================================================================
# 1. NVME PRESENTS
# =============================================================================
sep "NVMe detectes"

NVMES=()
while IFS= read -r dev; do
    SIZE=$(lsblk -d -o SIZE "$dev" 2>/dev/null | tail -1 | xargs)
    MODEL=$(lsblk -d -o MODEL "$dev" 2>/dev/null | tail -1 | xargs)
    NVMES+=("$dev")
    info "$dev  $SIZE  ${MODEL:-?}"
done < <(ls /dev/nvme*n1 2>/dev/null | sort)

[[ ${#NVMES[@]} -eq 0 ]] && err "Aucun NVMe trouve"
[[ ${#NVMES[@]} -lt 2 ]] && warn "Un seul NVMe -- boot_pool et fast_pool sur le meme disque est possible"

# =============================================================================
# 2. PARTITION EFI
#    Cherche toutes les partitions vfat ayant un repertoire EFI/ ou efi/.
#    Affiche une liste numerotee, propose la premiere comme defaut.
#    Si aucune trouvee : saisie manuelle.
# =============================================================================
sep "Recherche de la partition EFI"

EFI_TMP="/mnt/efi-detect-$$"
mkdir -p "$EFI_TMP"

_cleanup_efi() { umount "$EFI_TMP" 2>/dev/null; rmdir "$EFI_TMP" 2>/dev/null; }
trap _cleanup_efi EXIT

# Collecter TOUTES les partitions vfat avec repertoire EFI/
declare -a EFI_CANDIDATES=()
declare -a EFI_DESCS=()

for nvme in "${NVMES[@]}"; do
    for part in "${nvme}p"*; do
        [[ -b "$part" ]] || continue
        PTYPE=$(blkid -s TYPE -o value "$part" 2>/dev/null || true)
        [[ "$PTYPE" == "vfat" ]] || continue
        mount -t vfat -o ro "$part" "$EFI_TMP" 2>/dev/null || continue
        # Chercher EFI/ ou efi/ (insensible a la casse via find)
        EFI_DIR=$(find "$EFI_TMP" -maxdepth 1 -iname "efi" -type d 2>/dev/null | head -1)
        if [[ -n "$EFI_DIR" ]]; then
            # Collecter le contenu pour la description
            ENTRIES=$(find "$EFI_DIR" -maxdepth 2 \( -name "*.efi" -o -name "*.EFI" \) 2>/dev/null \
                | sed "s|$EFI_TMP||" | tr '\n' ' ' | xargs)
            SIZE=$(lsblk -d -o SIZE "$part" 2>/dev/null | tail -1 | xargs)
            LABEL=$(blkid -s LABEL -o value "$part" 2>/dev/null || echo "")
            EFI_CANDIDATES+=("$part")
            EFI_DESCS+=("$part  ${SIZE}  ${LABEL:+[$LABEL] }  ${ENTRIES:-repertoire EFI vide}")
        fi
        umount "$EFI_TMP" 2>/dev/null || true
    done
done

EFI_PART=""

if [[ ${#EFI_CANDIDATES[@]} -eq 0 ]]; then
    warn "Aucune partition EFI (vfat + EFI/) trouvee automatiquement"
    echo ""
    echo "  Partitions disponibles :"
    lsblk -o NAME,SIZE,FSTYPE,LABEL "${NVMES[@]}" 2>/dev/null | sed 's/^/    /'
    echo ""
    echo -n "  Saisir la partition EFI (ex: /dev/nvme0n1p1) : "
    read -r EFI_PART
    [[ -b "$EFI_PART" ]] || err "Partition introuvable : $EFI_PART"

elif [[ ${#EFI_CANDIDATES[@]} -eq 1 ]]; then
    # Une seule candidate -- confirmation rapide
    EFI_PART="${EFI_CANDIDATES[0]}"
    ok "Partition EFI detectee : $EFI_PART"
    info "${EFI_DESCS[0]}"
    echo -n "  Utiliser ${EFI_PART} comme partition EFI ? [O/n] : "
    read -r _CONFIRM
    if [[ "$_CONFIRM" =~ ^[Nn]$ ]]; then
        echo ""
        echo "  Partitions disponibles :"
        lsblk -o NAME,SIZE,FSTYPE,LABEL "${NVMES[@]}" 2>/dev/null | sed 's/^/    /'
        echo ""
        echo -n "  Saisir la partition EFI : "
        read -r EFI_PART
        [[ -b "$EFI_PART" ]] || err "Partition introuvable : $EFI_PART"
    fi

else
    # Plusieurs candidates -- menu
    echo ""
    echo "  Partitions EFI detectees :"
    for i in "${!EFI_CANDIDATES[@]}"; do
        echo "    $((i+1))) ${EFI_DESCS[$i]}"
    done
    echo ""
    echo -n "  Choix [1-${#EFI_CANDIDATES[@]}, defaut=1] : "
    read -r _IDX
    _IDX="${_IDX:-1}"
    if [[ "$_IDX" =~ ^[0-9]+$ ]] && (( _IDX >= 1 && _IDX <= ${#EFI_CANDIDATES[@]} )); then
        EFI_PART="${EFI_CANDIDATES[$((_IDX-1))]}"
    else
        warn "Choix invalide, utilisation du defaut : ${EFI_CANDIDATES[0]}"
        EFI_PART="${EFI_CANDIDATES[0]}"
    fi
    ok "Partition EFI selectionnee : $EFI_PART"
fi

# Verifier que la partition est bien montable en EFI
mount -t vfat -o ro "$EFI_PART" "$EFI_TMP" 2>/dev/null && {
    EFI_DIR=$(find "$EFI_TMP" -maxdepth 1 -iname "efi" -type d | head -1)
    if [[ -n "$EFI_DIR" ]]; then
        info "Contenu EFI :"
        find "$EFI_DIR" -maxdepth 2 \( -name "*.efi" -o -name "*.EFI" \) 2>/dev/null \
            | sed "s|$EFI_TMP||" | sed 's/^/      /'
    fi
    umount "$EFI_TMP" 2>/dev/null
} || warn "Impossible de monter $EFI_PART en lecture"

# ── NVME_A : NVMe parent de EFI_PART (disque pour efibootmgr) ─────────────────
# NVME_A = disque portant l'EFI. boot_pool peut être sur d'autres devices
# (mirror, stripe, SATA) — ne pas supposer de topologie fixe.
#
# Fallbacks séquentiels — NE PAS chainer les deux sed en une seule passe :
#   sed 's/p[0-9]*$//;s/[0-9]*$//' casse nvme0n1p1 → nvme0n1 → nvme0n  ← FAUX
# Logique correcte :
#   1. lsblk PKNAME (le plus fiable, retourne le disque parent réel)
#   2. strip pN final (NVMe : nvme0n1p1 → nvme0n1 ; ne change pas sda1)
#   3. si le nom n'a pas changé (SATA), strip digits (sda1 → sda)
NVME_A=$(lsblk -npo PKNAME "$EFI_PART" 2>/dev/null | head -1 | xargs || true)
if [[ -z "$NVME_A" ]] || [[ ! -b "$NVME_A" ]]; then
    _stripped=$(echo "$EFI_PART" | sed 's/p[0-9]\+$//')
    if [[ "$_stripped" != "$EFI_PART" ]]; then
        NVME_A="$_stripped"                          # NVMe : pN retiré
    else
        NVME_A=$(echo "$EFI_PART" | sed 's/[0-9]\+$//')  # SATA : digits retirés
    fi
fi
[[ -b "$NVME_A" ]] || err "Impossible de determiner le NVMe parent de $EFI_PART"
ok "NVMe-A (disque EFI) : $NVME_A"

# NVME_B = premier NVMe different de NVME_A
NVME_B=""
for nvme in "${NVMES[@]}"; do
    [[ "$nvme" != "$NVME_A" ]] && { NVME_B="$nvme"; break; }
done
[[ -n "$NVME_B" ]] && ok "NVMe-B : $NVME_B" || info "NVMe-B absent"

# ── Fonction : lister les devices feuilles d'un pool ZFS ──────────────────────
# Utilise zpool status (topologie reelle : mirror, stripe, raidz, vdev)
# Ne jamais supposer la topologie depuis les partitions du disque.
_zpool_devices() {
    local pool="$1"
    # Methode 1 : zpool list -Hv → lignes avec le device en $1
    zpool list -Hv "$pool" 2>/dev/null \
        | awk 'NF>=1 && ($1 ~ /^\/dev\// || $1 ~ /^nvme/ || $1 ~ /^sd/ || $1 ~ /^vd/) {print $1}'
    # Methode 2 : zpool status → parsing des lignes indentees de devices
    zpool status "$pool" 2>/dev/null \
        | awk '/^\t\t\t/{gsub(/[ \t]/,""); gsub(/\(.*\)/,""); if ($0 ~ /^[a-z\/]/) print $0}'
}

# ── BOOT_POOL_PART : devices reels de boot_pool ───────────────────────────────
BOOT_POOL_PART=""
BOOT_POOL_VDEVS=()

_collect_vdevs() {
    local pool="$1"
    local -n _arr="$2"  # nameref
    while IFS= read -r _dev; do
        [[ -z "$_dev" ]] && continue
        [[ "$_dev" == /dev/* ]] || _dev="/dev/$_dev"
        [[ -b "$_dev" ]] || continue
        # Dedupliquer
        local _already=0
        for _x in "${_arr[@]:-}"; do [[ "$_x" == "$_dev" ]] && _already=1 && break; done
        [[ $_already -eq 0 ]] && _arr+=("$_dev")
    done < <(_zpool_devices "$pool")
}

if zpool list boot_pool >/dev/null 2>&1; then
    _collect_vdevs boot_pool BOOT_POOL_VDEVS
    if [[ ${#BOOT_POOL_VDEVS[@]} -gt 0 ]]; then
        BOOT_POOL_PART="${BOOT_POOL_VDEVS[0]}"
        ok "boot_pool : ${#BOOT_POOL_VDEVS[@]} vdev(s) detectes"
        for _v in "${BOOT_POOL_VDEVS[@]}"; do info "  $_v"; done
    else
        warn "boot_pool importe mais vdevs non lus — fallback scan partitions"
        goto_fallback_boot=1
    fi
else
    goto_fallback_boot=1
fi

if [[ "${goto_fallback_boot:-0}" -eq 1 ]]; then
    # Pool non importe ou vdevs non lus : scan blkid sur tous les disques
    info "Scan zfs_member sur tous les disques..."
    for _d in "${NVMES[@]}" $(lsblk -lnpo NAME 2>/dev/null | grep -E '^/dev/sd[a-z]+$'); do
        for _p in "${_d}p"[0-9]* "${_d}"[0-9]*; do
            [[ -b "$_p" ]] || continue
            [[ "$_p" == "$EFI_PART" ]] && continue
            _pt=$(blkid -s TYPE -o value "$_p" 2>/dev/null || true)
            [[ "$_pt" == "zfs_member" ]] || continue
            _pl=$(blkid -s LABEL -o value "$_p" 2>/dev/null || true)
            info "  zfs_member : $_p  label=${_pl:-?}"
            if [[ -z "$BOOT_POOL_PART" ]] && \
               [[ "$_pl" == "boot_pool" || ("$_pl" != "fast_pool" && "$_pl" != "data_pool") ]]; then
                BOOT_POOL_PART="$_p"
                BOOT_POOL_VDEVS+=("$_p")
            fi
        done
    done
    [[ -n "$BOOT_POOL_PART" ]] \
        && ok "boot_pool candidat : $BOOT_POOL_PART" \
        || warn "boot_pool non trouve (normal au premier deploiement)"
fi

# ── DATA_DISKS : devices de data_pool ─────────────────────────────────────────
# Source de verite = zpool status data_pool (RAIDZ, mirror, SSD, NVMe...)
# Fallback : disques sd* non utilises par boot_pool/fast_pool
DATA_DISKS_STR=""
DATA_DISKS_ARR_DETECT=()

if zpool list data_pool >/dev/null 2>&1; then
    _collect_vdevs data_pool DATA_DISKS_ARR_DETECT
    # Pour data_pool on veut les disques entiers, pas les partitions
    _data_disks_full=()
    for _dev in "${DATA_DISKS_ARR_DETECT[@]:-}"; do
        _disk=$(lsblk -npo PKNAME "$_dev" 2>/dev/null | head -1 | xargs || true)
        if [[ -z "$_disk" ]] || [[ ! -b "$_disk" ]]; then
            _stripped=$(echo "$_dev" | sed 's/p[0-9]\+$//')
            if [[ "$_stripped" != "$_dev" ]]; then
                _disk="$_stripped"
            else
                _disk=$(echo "$_dev" | sed 's/[0-9]\+$//')
            fi
        fi
        [[ -n "$_disk" && -b "$_disk" ]] && _dev="$_disk"
        _dup=0
        for _x in "${_data_disks_full[@]:-}"; do [[ "$_x" == "$_dev" ]] && _dup=1 && break; done
        [[ $_dup -eq 0 ]] && _data_disks_full+=("$_dev")
    done
    DATA_DISKS_ARR_DETECT=("${_data_disks_full[@]:-}")
fi

if [[ ${#DATA_DISKS_ARR_DETECT[@]} -eq 0 ]]; then
    # Fallback : tous les sd* non utilises par boot_pool
    _used_devs="${BOOT_POOL_VDEVS[*]:-} ${EFI_PART:-}"
    while IFS= read -r _dev; do
        [[ -b "$_dev" ]] || continue
        [[ "$_used_devs" == *"$_dev"* ]] && continue
        DATA_DISKS_ARR_DETECT+=("$_dev")
    done < <(lsblk -lnpo NAME 2>/dev/null | grep -E '^/dev/sd[a-z]+$')
fi

for _d in "${DATA_DISKS_ARR_DETECT[@]:-}"; do
    DATA_DISKS_STR+="\"$_d\" "
done
DATA_DISKS_STR="${DATA_DISKS_STR% }"
[[ -n "$DATA_DISKS_STR" ]] \
    && info "Data disks detectes : $DATA_DISKS_STR" \
    || info "Aucun disque data detecte (data_pool facultatif)"


# =============================================================================
# 3. POOLS ZFS
# =============================================================================
sep "Pools ZFS"

modprobe zfs 2>/dev/null || true

IMPORTABLE=$(zpool import 2>/dev/null | grep "pool:" | awk '{print $2}' || true)
IMPORTED=$(zpool list -H -o name 2>/dev/null || true)

for pool in boot_pool fast_pool data_pool; do
    if echo "$IMPORTED" | grep -q "^${pool}$"; then
        SIZE=$(zpool list -H -o size "$pool" 2>/dev/null | xargs)
        HEALTH=$(zpool list -H -o health "$pool" 2>/dev/null | xargs)
        ok "$pool : importe  [$HEALTH $SIZE]"
    elif echo "$IMPORTABLE" | grep -q "^${pool}$"; then
        warn "$pool : importable (non encore importe)"
    else
        warn "$pool : non trouve (normal avant creation)"
    fi
done

# =============================================================================
# 4. IMAGES DANS boot_pool
# =============================================================================
sep "Images dans boot_pool"

# ─── MONTAGE DE boot_pool + boot_pool/images POUR SCAN DES IMAGES ────────────
# Sur Debian live, /boot appartient au live CD → on monte sur /mnt/zbm-live
# boot_pool/images est un dataset enfant ZFS — doit être monté explicitement
# avec "zfs mount boot_pool/images" après le montage de boot_pool (zpool import -N
# ne monte pas les enfants automatiquement).

ZBM_LIVE_MNT="${ZBM_BOOT:-/mnt/zbm/boot}"
BOOT_MP=""
BOOT_IMPORTED=0
_DETECT_BOOT_MOUNTED=0
_DETECT_IMAGES_MOUNTED=0

_cleanup_detect_boot() {
    # Démonter boot_pool/images AVANT boot_pool (enfant ZFS)
    [[ $_DETECT_IMAGES_MOUNTED -eq 1 ]] && \
        zfs unmount boot_pool/images 2>/dev/null || true
    [[ $_DETECT_BOOT_MOUNTED -eq 1 ]] && \
        umount "$ZBM_LIVE_MNT" 2>/dev/null || true
}
trap _cleanup_detect_boot EXIT

# Montage de boot_pool/images une fois boot_pool monté
_mount_images() {
    [[ -n "$BOOT_MP" ]] || return 0
    if zfs list boot_pool/images >/dev/null 2>&1; then
        if mountpoint -q "$BOOT_MP/images" 2>/dev/null; then
            : # déjà monté (cas où boot_pool était déjà là)
        else
            mkdir -p "$BOOT_MP/images"
            if zfs mount boot_pool/images 2>/dev/null; then
                _DETECT_IMAGES_MOUNTED=1
                ok "boot_pool/images → $BOOT_MP/images"
            else
                warn "boot_pool/images : zfs mount échoué — images inaccessibles"
            fi
        fi
    else
        info "boot_pool/images absent (premier déploiement — datasets-check.sh --initial)"
    fi
}

# 1. boot_pool déjà monté ?
_cur=$(zfs mount 2>/dev/null | awk '$1=="boot_pool"{print $2}' | head -1 || true)
if [[ -n "$_cur" ]]; then
    BOOT_MP="$_cur"
    BOOT_IMPORTED=1
    info "boot_pool déjà monté : $BOOT_MP"
    _mount_images

# 2. Importé mais pas monté → monter sur /mnt/zbm-live
elif echo "$IMPORTED" | grep -q "^boot_pool$"; then
    BOOT_IMPORTED=1
    mkdir -p "$ZBM_LIVE_MNT"
    if mount -t zfs boot_pool "$ZBM_LIVE_MNT" 2>/dev/null; then
        BOOT_MP="$ZBM_LIVE_MNT"
        _DETECT_BOOT_MOUNTED=1
        ok "boot_pool monté → $BOOT_MP"
        _mount_images
    else
        warn "boot_pool importé mais non montable (verrou ?)"
    fi

# 3. Importable mais pas encore importé → import + montage
elif echo "$IMPORTABLE" | grep -q "^boot_pool$"; then
    zpool import -N boot_pool 2>/dev/null && BOOT_IMPORTED=1
    mkdir -p "$ZBM_LIVE_MNT"
    if mount -t zfs boot_pool "$ZBM_LIVE_MNT" 2>/dev/null; then
        BOOT_MP="$ZBM_LIVE_MNT"
        _DETECT_BOOT_MOUNTED=1
        ok "boot_pool importé et monté → $BOOT_MP"
        _mount_images
    fi

# 4. Pas de boot_pool → scan impossible (normal au 1er déploiement)
else
    info "boot_pool absent — aucune image à scanner (normal au premier déploiement)"
fi

# Sanité : ne jamais utiliser /boot du live
[[ "$BOOT_MP" == "/boot" ]] && BOOT_MP="$ZBM_LIVE_MNT"

ROOTFS_FILES=()
KERNEL_FILES=()
declare -A IMAGE_KVER=()  # kernel file -> kver

for imgtype in kernel initramfs modules rootfs; do
    case "$imgtype" in
        kernel)    subdir="images/kernels" ;;
        initramfs) subdir="images/initramfs" ;;
        modules)   subdir="images/modules" ;;
        rootfs)    subdir="images/rootfs" ;;
    esac
    dir="$BOOT_MP/$subdir"
    [[ -d "$dir" ]] || continue
    count=0
    while IFS= read -r f; do
        [[ -f "$f" && "$f" != *.meta ]] || continue
        sz=$(du -sh "$f" 2>/dev/null | cut -f1)
        ok "$(basename "$f")  ($sz)"
        [[ "$imgtype" == "rootfs" ]] && ROOTFS_FILES+=("$f")
        if [[ "$imgtype" == "kernel" ]]; then
            KERNEL_FILES+=("$f")
            # Lire la kver depuis le sidecar .meta
            kv=$(python3 -c "import json; d=json.load(open('${f}.meta')); print(d.get('kernel_ver',''))" 2>/dev/null || true)
            [[ -n "$kv" ]] && IMAGE_KVER["$f"]="$kv"
        fi
        count=$((count+1))
    done < <(find "$dir" -maxdepth 1 -type f 2>/dev/null | sort)
    [[ $count -eq 0 ]] && info "(aucun $imgtype dans boot_pool -- normal au premier deploiement)"
done

# Chercher rootfs sur media si absent de boot_pool
if [[ ${#ROOTFS_FILES[@]} -eq 0 ]]; then
    for mnt in /run/live/medium /live/image /cdrom /media /mnt; do
        [[ -d "$mnt" ]] || continue
        while IFS= read -r f; do
            [[ -f "$f" ]] || continue
            ROOTFS_FILES+=("$f")
            info "Rootfs externe detecte : $f"
        done < <(find "$mnt" -name "rootfs*.sfs" -maxdepth 5 2>/dev/null)
    done
fi

ROOTFS_SRC_NEW="auto"
[[ ${#ROOTFS_FILES[@]} -gt 0 ]] && {
    ROOTFS_SRC_NEW="${ROOTFS_FILES[0]}"
    ok "${#ROOTFS_FILES[@]} rootfs disponible(s)"
} || info "Aucun rootfs -- placer dans $BOOT_MP/images/rootfs/ ou sur le support live"

# KERNEL_VER depuis le meta du kernel le plus recent
KVER_FROM_BOOT=""
if [[ ${#KERNEL_FILES[@]} -gt 0 ]]; then
    LATEST_KERNEL=$(ls -t "${KERNEL_FILES[@]}" 2>/dev/null | head -1)
    KVER_FROM_BOOT="${IMAGE_KVER[$LATEST_KERNEL]:-}"
fi

# =============================================================================
# 5. SYSTEMES EXISTANTS
# =============================================================================
sep "Systemes detectes"

SYSTEMS_DETECTED=()
if echo "$IMPORTED" | grep -q "^fast_pool$"; then
    while IFS= read -r ds; do
        sysname="${ds#fast_pool/overlay-}"
        [[ -n "$sysname" && "$sysname" != "failsafe" ]] && SYSTEMS_DETECTED+=("$sysname")
    done < <(zfs list -H -o name 2>/dev/null | grep '^fast_pool/overlay-' | grep -v 'failsafe' || true)
fi

if [[ ${#SYSTEMS_DETECTED[@]} -gt 0 ]]; then
    for s in "${SYSTEMS_DETECTED[@]}"; do ok "Systeme ZFS detecte : $s"; done
else
    info "Aucun systeme detecte dans fast_pool (normal au premier deploiement)"
fi

# =============================================================================
# 6. LECTURE DES VALEURS EXISTANTES DE config.sh (a preserver)
# =============================================================================

SYSTEMS_PREV=()
KERNEL_LABEL_PREV=""
KERNEL_VER_PREV=""
INIT_TYPE_PREV="zbm"
ROOTFS_LABEL_PREV="gentoo"
STREAM_KEY_PREV=""
STREAM_RES_PREV="1920x1080"
STREAM_FPS_PREV="30"
STREAM_BITRATE_PREV="4500k"
STREAM_DELAY_PREV="30"
NETWORK_MODE_PREV="dhcp"
NETWORK_IFACE_PREV="auto"
NETWORK_IP_PREV=""
NETWORK_GW_PREV=""
NETWORK_DNS_PREV=""

if [[ -f "$CONF_FILE" ]]; then
    # Lire chaque valeur avec grep simple -- evite sourcer un fichier potentiellement corrompu
    _read_conf() {
        local key="$1" default="${2:-}"
        grep "^${key}=" "$CONF_FILE" 2>/dev/null \
            | head -1 | sed 's/^[^=]*=//;s/^"//;s/"$//' || echo "$default"
    }
    KERNEL_LABEL_PREV=$(_read_conf KERNEL_LABEL "")
    KERNEL_VER_PREV=$(_read_conf KERNEL_VER "")
    INIT_TYPE_PREV=$(_read_conf INIT_TYPE "zbm")
    ROOTFS_LABEL_PREV=$(_read_conf ROOTFS_LABEL "gentoo")
    STREAM_KEY_PREV=$(_read_conf STREAM_KEY "")
    STREAM_RES_PREV=$(_read_conf STREAM_RESOLUTION "1920x1080")
    STREAM_FPS_PREV=$(_read_conf STREAM_FPS "30")
    STREAM_BITRATE_PREV=$(_read_conf STREAM_BITRATE "4500k")
    STREAM_DELAY_PREV=$(_read_conf STREAM_DELAY_SEC "30")
    NETWORK_MODE_PREV=$(_read_conf NETWORK_MODE "dhcp")
    NETWORK_IFACE_PREV=$(_read_conf NETWORK_IFACE "auto")
    NETWORK_IP_PREV=$(_read_conf NETWORK_IP "")
    NETWORK_GW_PREV=$(_read_conf NETWORK_GW "")
    NETWORK_DNS_PREV=$(_read_conf NETWORK_DNS "")

    # Lire SYSTEMS via sous-shell isole (tableau bash)
    _raw=$(env CONF="$CONF_FILE" bash -c 'source "$CONF" 2>/dev/null; printf "%s\n" "${SYSTEMS[@]:-}"' 2>/dev/null || true)
    while IFS= read -r s; do
        [[ -n "$s" ]] && SYSTEMS_PREV+=("$s")
    done <<< "$_raw"
fi

# KERNEL_VER : priorite -> fichier .meta boot_pool > config.sh existant
# On ne prend JAMAIS uname -r (= kernel du live, pas le kernel cible)
KERNEL_VER_FINAL="${KVER_FROM_BOOT:-${KERNEL_VER_PREV:-}}"

# Merger SYSTEMS_PREV + SYSTEMS_DETECTED, sans doublons, min="systeme1"
declare -A _seen=()
SYSTEMS_MERGED=()
for s in "${SYSTEMS_PREV[@]:-}" "${SYSTEMS_DETECTED[@]:-}"; do
    [[ -z "$s" ]] && continue
    [[ -n "${_seen[$s]:-}" ]] && continue
    _seen[$s]=1
    SYSTEMS_MERGED+=("$s")
done
[[ ${#SYSTEMS_MERGED[@]} -eq 0 ]] && SYSTEMS_MERGED=("systeme1")

# Construire SYSTEMS=("a" "b") -- pure ASCII
SYSTEMS_STR="("
for s in "${SYSTEMS_MERGED[@]}"; do
    SYSTEMS_STR+="\"${s}\" "
done
SYSTEMS_STR="${SYSTEMS_STR% })"

# DATA_DISKS=(...) -- pure ASCII
DATA_DISKS_ARR="(${DATA_DISKS_STR})"

# Reseau : lignes commentees si static
if [[ "$NETWORK_MODE_PREV" == "static" && -n "$NETWORK_IP_PREV" ]]; then
    NETWORK_STATIC_LINES="NETWORK_IP=\"${NETWORK_IP_PREV}\""$'\n'"NETWORK_GW=\"${NETWORK_GW_PREV}\""$'\n'"NETWORK_DNS=\"${NETWORK_DNS_PREV}\""
else
    NETWORK_STATIC_LINES="# NETWORK_IP=\"192.168.1.10/24\""$'\n'"# NETWORK_GW=\"192.168.1.1\""$'\n'"# NETWORK_DNS=\"1.1.1.1\""
fi

# =============================================================================
# 7. ECRITURE DE config.sh -- pur ASCII, aucun UTF-8
# =============================================================================
{
printf '#!/bin/bash\n'
printf '# =============================================================================\n'
printf '# deploy/config.sh\n'
printf '#\n'
printf '# Source de verite de la configuration ZFSBootMenu.\n'
printf '# Genere par lib/detect.sh le %s\n' "$(date '+%Y-%m-%d %H:%M:%S')"
printf '# Editable manuellement.\n'
printf '#\n'
printf '# Apres modification de SYSTEMS :\n'
printf '#   etape 2 (datasets-check.sh) pour creer les datasets\n'
printf '#   etape 7 (presets.sh)        pour generer les entrees de boot\n'
printf '# =============================================================================\n'
printf '\n'
printf '# --- SYSTEMES ---\n'
printf '# Un systeme = datasets ZFS isoles :\n'
printf '#   fast_pool/overlay-<s>   canmount=noauto  (upper OverlayFS)\n'
printf '#   fast_pool/overlay-<s>   canmount=noauto  mountpoint=none  (upper OverlayFS)\n'
printf '#   (pas de var-/log-/tmp- : architecture overlay, lower=rootfs.sfs)\n'
printf '#\n'
printf '# "failsafe" est reserve -- ne pas l'"'"'ajouter ici.\n'
printf 'SYSTEMS=%s\n' "$SYSTEMS_STR"
printf '\n'
printf '# --- POOLS ZFS ---\n'
printf 'BOOT_POOL="boot_pool"\n'
printf 'FAST_POOL="fast_pool"\n'
printf 'DATA_POOL="data_pool"\n'
printf '\n'
printf '# --- MATERIEL (detecte par detect.sh) ---\n'
printf 'NVME_A="%s"\n'          "${NVME_A}"
printf 'NVME_B="%s"\n'          "${NVME_B:-}"
printf 'EFI_PART="%s"\n'        "${EFI_PART}"
printf 'BOOT_POOL_PART="%s"\n'  "${BOOT_POOL_PART:-}"
# BOOT_MNT dans config.sh : point de montage de boot_pool sur le live
# Les scripts deploy utilisent zbm_locate_boot() → détection dynamique
# Ne jamais hardcoder /boot (occupé sur Debian live)
_boot_mnt_for_config="${BOOT_MP:-${ZBM_BOOT:-/mnt/zbm/boot}}"
printf 'EFI_MNT="%s/efi"\n'  "$_boot_mnt_for_config"
printf 'BOOT_MNT="%s"\n'     "$_boot_mnt_for_config"
printf '# Les scripts deploy utilisent zbm_locate_boot() -- BOOT_MNT est indicatif seulement\n' 
printf 'RAIDZ_TYPE="raidz2"\n'
printf 'DATA_DISKS=%s\n'        "${DATA_DISKS_ARR}"
printf '\n'
printf '# --- KERNEL ---\n'
printf '# KERNEL_LABEL : identifiant libre  ex: generic-6.12\n'
printf '# KERNEL_VER   : version exacte -- ecrite par kernel.sh, lue par initramfs.sh/presets.sh\n'
printf '# Vide = kernel.sh demandera interactivement\n'
printf 'KERNEL_LABEL="%s"\n'    "${KERNEL_LABEL_PREV:-}"
printf 'KERNEL_VER="%s"\n'      "${KERNEL_VER_FINAL:-}"
printf '\n'
printf '# --- INITRAMFS ---\n'
printf '# zbm | zbm-stream | minimal | custom-<n>   (vide = initramfs.sh demande)\n'
printf 'INIT_TYPE="%s"\n'       "${INIT_TYPE_PREV}"
printf '\n'
printf '# --- ROOTFS ---\n'
printf '# ROOTFS_LABEL : label  ex: gentoo  arch  debian-base\n'
printf '# ROOTFS_SRC   : "auto" = cherche *.sfs sur le support live, ou chemin absolu\n'
printf 'ROOTFS_LABEL="%s"\n'    "${ROOTFS_LABEL_PREV}"
printf 'ROOTFS_SRC="%s"\n'      "${ROOTFS_SRC_NEW}"
printf '\n'
printf '# --- STREAM YOUTUBE ---\n'
printf 'STREAM_KEY="%s"\n'          "${STREAM_KEY_PREV}"
printf 'STREAM_RESOLUTION="%s"\n'   "${STREAM_RES_PREV}"
printf 'STREAM_FPS=%s\n'            "${STREAM_FPS_PREV}"
printf 'STREAM_BITRATE="%s"\n'      "${STREAM_BITRATE_PREV}"
printf 'STREAM_DELAY_SEC=%s\n'      "${STREAM_DELAY_PREV}"
printf '\n'
printf '# --- RESEAU ---\n'
printf '# NETWORK_MODE : dhcp | static | none\n'
printf 'NETWORK_MODE="%s"\n'    "${NETWORK_MODE_PREV}"
printf 'NETWORK_IFACE="%s"\n'   "${NETWORK_IFACE_PREV}"
printf '%s\n'                   "${NETWORK_STATIC_LINES}"
printf '\n'
printf '# --- REGLE MOUNTPOINTS (ne pas modifier) ---\n'
printf '# Tous fast_pool/* : canmount=noauto -- jamais monte par "zfs mount -a"\n'
printf '# Montage reel : initramfs-init via "mount -t zfs <ds> <chemin>"\n'
printf '# Guard "mountpoint -q" anti-double-montage sur chaque point de montage.\n'
} > "$CONF_FILE"

ok "config.sh ecrit : $CONF_FILE"
ok "Systemes : ${SYSTEMS_MERGED[*]}"
[[ -n "$KERNEL_VER_FINAL" ]] && ok "KERNEL_VER preservee : $KERNEL_VER_FINAL" \
    || info "KERNEL_VER vide -- sera definie par kernel.sh"

echo ""
sep "Resume"
echo "  NVMe-A      : $NVME_A"
echo "  NVMe-B      : ${NVME_B:-non trouve}"
echo "  EFI         : $EFI_PART"
echo "  boot_pool   : ${BOOT_POOL_PART:-non trouve (normal si non cree)}"
echo "  Data SATA   : ${DATA_DISKS_STR:-aucun}"
echo "  Systemes    : ${SYSTEMS_MERGED[*]}"
echo "  Kernels     : ${#KERNEL_FILES[@]} dans boot_pool"
echo "  Rootfs      : ${#ROOTFS_FILES[@]} disponible(s)"
echo ""
warn "Verifier et ajuster deploy/config.sh avant de continuer"
