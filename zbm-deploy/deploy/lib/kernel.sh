#!/bin/bash
# =============================================================================
# lib/kernel.sh — Installer un kernel + modules dans boot_pool
#
# SEPARATION FONDAMENTALE :
#   SOURCE  = live system / rootfs squashfs  (d'où vient le kernel)
#   DEST    = boot_pool                      (où il est installé)
#
# boot_pool est localisé DYNAMIQUEMENT (zfs mount) et non assumé a /boot.
# /boot pendant le live = boot du live, pas boot_pool.
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/naming.sh"
CONF="$(dirname "$SCRIPT_DIR")/config.sh"
[[ -f "$CONF" ]] && source "$CONF" || true

GREEN='\033[1;32m'; YELLOW='\033[1;33m'; RED='\033[1;31m'
CYAN='\033[1;36m'; BOLD='\033[1m'; NC='\033[0m'
ok()   { echo -e "  ${GREEN}OK $*${NC}"; }
warn() { echo -e "  ${YELLOW}WARN $*${NC}"; }
err()  { echo -e "  ${RED}ERR $*${NC}"; exit 1; }
info() { echo -e "  ${CYAN}    $*${NC}"; }

TODAY="${IMAGE_DATE:-$(date +%Y%m%d)}"
NO_MODULES=0
FROM_ROOTFS=""
KERNEL_SRC=""
MODULES_SRC=""
_MOUNTED_BOOT=0
TMP_MNT=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --label)       KERNEL_LABEL="$2"; shift 2 ;;
        --no-modules)  NO_MODULES=1; shift ;;
        --from-rootfs) FROM_ROOTFS="$2"; shift 2 ;;
        --kernel-src)  KERNEL_SRC="$2"; shift 2 ;;
        --modules-src) MODULES_SRC="$2"; shift 2 ;;
        --date)        TODAY="$2"; shift 2 ;;
        *) err "Argument inconnu : $1" ;;
    esac
done

cleanup() {
    zbm_cleanup_boot
    [[ -n "$TMP_MNT" ]] && { umount "$TMP_MNT" 2>/dev/null; rmdir "$TMP_MNT" 2>/dev/null; } || true
}
trap cleanup EXIT

# Localisation de boot_pool — utilise zbm_locate_boot() de naming.sh
# Sur Debian live /boot est occupé → boot_pool monté sur ${ZBM_BOOT:-/mnt/zbm/boot}
zbm_locate_boot || err "boot_pool introuvable — vérifiez les pools ZFS"
info "boot_pool -> $BOOT"

# =============================================================================
# LABEL
# =============================================================================
# =============================================================================
# CHOIX DU KERNEL : afficher la liste des kernels déjà installés dans boot_pool
# L'utilisateur peut choisir un existant ou en installer un nouveau.
# =============================================================================
if [[ -z "${KERNEL_LABEL:-}" ]]; then
    echo ""
    echo -e "  ${BOLD}Kernels disponibles dans boot_pool${NC}"
    PREFILL="${KERNEL_LABEL:-}"
    SEL=$(zbm_select_kernel --allow-new --label "$PREFILL") || err "Aucun kernel sélectionné"
    if [[ "$SEL" == "new"* ]]; then
        echo ""
        echo -e "  ${BOLD}Installer un nouveau kernel${NC}"
        echo "  Format du label : <type>-<version>  ex: generic-6.12  custom-i5-6.12"
        echo -n "  Label : "
        read -r KERNEL_LABEL
        [[ -n "${KERNEL_LABEL:-}" ]] || err "KERNEL_LABEL requis"
        info "Nouveau kernel à installer : label=${KERNEL_LABEL}"
    else
        IFS='|' read -r _KPATH KERNEL_LABEL _KDATE _KVER <<< "$SEL"
        ok "Kernel sélectionné : kernel-${KERNEL_LABEL}-${_KDATE}  kver=${_KVER}"
        # Si le kernel existe déjà et que l'utilisateur le ré-sélectionne,
        # on le copie quand même (mise à jour possible depuis un nouveau live).
    fi
fi
[[ -n "${KERNEL_LABEL:-}" ]] || err "KERNEL_LABEL requis"

KERNEL_DST=$(zbm_path kernel "" "$KERNEL_LABEL" "$TODAY")
MODULES_DST=$(zbm_path modules "" "$KERNEL_LABEL" "$TODAY")

echo ""
echo -e "  ${BOLD}Parametres${NC}"
echo "  Label    : $KERNEL_LABEL"
echo "  Kernel-> : $KERNEL_DST"
[[ $NO_MODULES -eq 0 ]] && echo "  Modules->: $MODULES_DST"

mkdir -p "$(zbm_dir kernel)" "$(zbm_dir modules)"

for dst_file in "$KERNEL_DST" "$MODULES_DST"; do
    [[ -f "$dst_file" ]] || continue
    warn "$(basename "$dst_file") existe deja"
    echo -n "  Ecraser ? [o/N] : "
    read -r CONFIRM
    [[ "$CONFIRM" =~ ^[Oo]$ ]] || { ok "Annule"; exit 0; }
done

# =============================================================================
# MONTAGE TEMPORAIRE --from-rootfs
# =============================================================================
if [[ -n "$FROM_ROOTFS" ]]; then
    [[ -f "$FROM_ROOTFS" ]] || err "Rootfs introuvable : $FROM_ROOTFS"
    file "$FROM_ROOTFS" | grep -qi "squashfs" || warn "Pas un squashfs valide"
    TMP_MNT=$(mktemp -d /tmp/zbm-rootfs-XXXX)
    mount -t squashfs -o loop,ro "$FROM_ROOTFS" "$TMP_MNT" \
        || err "Impossible de monter $FROM_ROOTFS"
    info "Rootfs monte : $FROM_ROOTFS -> $TMP_MNT"
fi

# =============================================================================
# 1. KERNEL SOURCE
# Chercher dans le LIVE, PAS dans boot_pool (qui est la destination)
# =============================================================================
echo ""
echo "  Recherche du kernel source (live / rootfs)..."

if [[ -z "${KERNEL_SRC:-}" ]]; then
    declare -a SEARCH_DIRS=()

    # a) Rootfs squashfs monte
    [[ -n "$TMP_MNT" ]] && SEARCH_DIRS+=("$TMP_MNT/boot")

    # b) Support live Debian/Ubuntu
    for live_dir in \
        /run/live/medium/live \
        /run/live/medium/boot \
        /live/image/live \
        /cdrom/live \
        /media/cdrom/live; do
        [[ -d "$live_dir" ]] && SEARCH_DIRS+=("$live_dir")
    done

    # c) /boot du live SEULEMENT si != boot_pool
    if [[ "$BOOT" != "/boot" ]] && [[ -d "/boot" ]]; then
        SEARCH_DIRS+=("/boot")
    fi

    for d in "${SEARCH_DIRS[@]:-}"; do
        [[ -d "$d" ]] || continue
        for pattern in "vmlinuz-*" "vmlinuz" "kernel-*" "bzImage"; do
            for f in "$d"/$pattern; do
                [[ -f "$f" ]] && { KERNEL_SRC="$f"; break 3; }
            done
        done
    done

    if [[ -z "${KERNEL_SRC:-}" ]]; then
        echo "  Kernel non trouve automatiquement."
        echo "  Repertoires cherches : ${SEARCH_DIRS[*]:-aucun}"
        echo -n "  Chemin vers vmlinuz : "
        read -r KERNEL_SRC
        [[ -f "$KERNEL_SRC" ]] || err "Introuvable : $KERNEL_SRC"
    fi
fi

KVER=$(basename "$KERNEL_SRC" | sed 's/^vmlinuz-//')
[[ "$KVER" == "vmlinuz" || "$KVER" == "bzImage" ]] && KVER="unknown"
info "Source : $KERNEL_SRC  (kver: $KVER)"

cp "$KERNEL_SRC" "$KERNEL_DST"
chmod 444 "$KERNEL_DST"
ok "$(basename "$KERNEL_DST")  ($(du -sh "$KERNEL_DST" | cut -f1))"

# =============================================================================
# 2. MODULES SQUASHFS
# Chercher dans le LIVE (/lib/modules/<kver>), PAS dans boot_pool
# =============================================================================
if [[ $NO_MODULES -eq 0 ]]; then
    echo ""
    echo "  Recherche des modules kernel (live / rootfs)..."

    if [[ -z "${MODULES_SRC:-}" ]]; then
        declare -a MOD_DIRS=()
        [[ -n "$TMP_MNT" ]] && MOD_DIRS+=("$TMP_MNT/lib/modules")
        MOD_DIRS+=("/lib/modules")

        for d in "${MOD_DIRS[@]:-}"; do
            [[ -d "$d" ]] || continue
            if [[ "$KVER" != "unknown" ]]; then
                # Chercher d'abord la correspondance EXACTE (ex: 6.19.5-custom)
                if [[ -d "$d/$KVER" ]]; then
                    MODULES_SRC="$d/$KVER"; break
                fi
                # Puis correspondance partielle (suffixe distro, ex: 6.19.5-custom-amd64)
                KVER_DIR=$(ls "$d" 2>/dev/null | grep -F "$KVER" | head -1 || true)
                [[ -n "$KVER_DIR" ]] && { MODULES_SRC="$d/$KVER_DIR"; break; }
                # NE PAS tomber sur le premier venu (risque live 6.12) si KVER est connu
            else
                # KVER inconnu : prendre le plus récent et avertir
                FIRST=$(ls -t "$d" 2>/dev/null | head -1 || true)
                [[ -n "$FIRST" ]] && { MODULES_SRC="$d/$FIRST"; break; }
            fi
        done
    fi

    if [[ -n "${MODULES_SRC:-}" ]] && [[ -d "$MODULES_SRC" ]]; then
        # Ne mettre à jour KVER que s'il était inconnu — jamais écraser un KVER
        # valide (ex: 6.19.5-custom) avec le nom du répertoire live (ex: 6.12.x)
        [[ "$KVER" == "unknown" ]] && KVER=$(basename "$MODULES_SRC")
        info "Source modules : $MODULES_SRC"
        echo -n "  Construction modules.sfs..."
        mksquashfs "$MODULES_SRC" "$MODULES_DST" \
            -comp zstd -Xcompression-level 6 -noappend -quiet
        chmod 444 "$MODULES_DST"
        echo " OK  ($(du -sh "$MODULES_DST" | cut -f1))"
        ok "$(basename "$MODULES_DST")"
    else
        warn "Modules introuvables -- modules.sfs non genere"
        NO_MODULES=1
    fi
fi

# =============================================================================
# 3. META
# =============================================================================
zbm_write_meta "$KERNEL_DST" "kernel_ver=${KVER}" "kernel_label=${KERNEL_LABEL}" "builder=kernel.sh"
[[ $NO_MODULES -eq 0 ]] && [[ -f "$MODULES_DST" ]] && \
    zbm_write_meta "$MODULES_DST" "kernel_ver=${KVER}" "kernel_label=${KERNEL_LABEL}" "builder=kernel.sh"
ok "Sidecars .meta"

# Ecrire KERNEL_VER et KERNEL_LABEL dans config.sh pour que initramfs.sh
# et presets.sh puissent les lire sans re-demander
_update_conf() {
    local key="$1" val="$2" conf="$3"
    [[ -f "$conf" ]] || return
    if grep -q "^${key}=" "$conf"; then
        # Remplacer la valeur existante (sed inline portable)
        sed -i "s|^${key}=.*|${key}=\"${val}\"|" "$conf"
    else
        printf '%s="%s"
' "$key" "$val" >> "$conf"
    fi
}
if [[ -f "$CONF" ]]; then
    _update_conf "KERNEL_VER"   "$KVER"         "$CONF"
    _update_conf "KERNEL_LABEL" "$KERNEL_LABEL" "$CONF"
    ok "KERNEL_VER=${KVER} ecrit dans config.sh"
fi

# =============================================================================
# 4. RECAP
# =============================================================================
echo ""
echo "  Kernels dans boot_pool :"
for f in "$(zbm_dir kernel)"/kernel-*; do
    [[ -f "$f" ]] && [[ "$f" != *.meta ]] || continue
    kv=$(zbm_read_meta "$f" "kernel_ver" 2>/dev/null || true)
    printf "    %-42s  kver=%s\n" "$(basename "$f")" "${kv:-?}"
done
echo ""
echo "  Modules dans boot_pool :"
for f in "$(zbm_dir modules)"/modules-*; do
    [[ -f "$f" ]] && [[ "$f" != *.meta ]] || continue
    echo "    $(basename "$f")  ($(du -sh "$f" | cut -f1))"
done
echo ""
echo -e "  ${CYAN}Prochaine etape : lib/initramfs.sh${NC}"
