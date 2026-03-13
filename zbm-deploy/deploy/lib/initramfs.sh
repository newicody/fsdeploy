#!/bin/bash
# =============================================================================
# lib/initramfs.sh — Construction d'un initramfs SANS dracut
#
# POURQUOI PAS DRACUT :
#   - Notre init est 100% custom (initramfs-init ou initramfs-stream-init)
#   - Les modules kernel viennent de modules.sfs monté au boot, pas de l'initramfs
#   - dracut a besoin de la version du kernel CIBLE pour inclure les bons modules
#   - En live, uname -r = kernel live != kernel cible => erreur de construction
#   - Solution : on construit le cpio directement, zéro dépendance à la kver
#
# CONTENU DE L'INITRAMFS :
#   /init                   Notre script d'init (initramfs-init ou stream-init)
#   /bin/                   Binaires essentiels copiés du live (busybox ou individuels)
#   /lib/ /lib64/           Libs partagées pour zfs, zpool, mount, mountpoint, etc.
#   /proc /sys /dev /run    Points de montage
#   /mnt/{boot,lower,fast,merged,modloop,python,tmp}  Points de montage initramfs
#
# Les modules NE SONT PAS dans l'initramfs — ils viennent de modules.sfs.
#
# Types d'init :
#   zbm         Notre init complet : overlay + pivot_root + Python TUI
#   zbm-stream  Variante flux vidéo seul, sans TUI
#   minimal     Init natif noyau (dracut standard) — seul cas qui a besoin de dracut
#   custom-<n>  Init personnalisé
#
# Variables (depuis config.sh ou environnement) :
#   INIT_TYPE    zbm | zbm-stream | minimal | custom-<n>
#   IMAGE_DATE   YYYYMMDD
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/naming.sh"
CONF="$(dirname "$SCRIPT_DIR")/config.sh"
[[ -f "$CONF" ]] && source "$CONF" || true
# Racine du projet = 2 niveaux au-dessus de deploy/lib/
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

GREEN='\033[1;32m'; YELLOW='\033[1;33m'; RED='\033[1;31m'
CYAN='\033[1;36m'; BOLD='\033[1m'; NC='\033[0m'
ok()   { echo -e "  ${GREEN}OK $*${NC}"; }
warn() { echo -e "  ${YELLOW}WARN $*${NC}"; }
err()  { echo -e "  ${RED}ERR $*${NC}"; exit 1; }
info() { echo -e "  ${CYAN}    $*${NC}"; }

TODAY="${IMAGE_DATE:-$(date +%Y%m%d)}"
INIT_SRC="$PROJECT_ROOT/initramfs-init"
INIT_STREAM_SRC="$PROJECT_ROOT/initramfs-stream-init"
# Localisation de boot_pool — utilise zbm_locate_boot() de naming.sh
# Sur Debian live /boot est occupé → boot_pool monté sur ${ZBM_BOOT:-/mnt/zbm/boot}
_MOUNTED_BOOT=0  # rétrocompat

cleanup() {
    zbm_cleanup_boot
    [[ -n "${INJECT:-}" ]] && rm -rf "$INJECT" 2>/dev/null || true
}
trap cleanup EXIT
zbm_locate_boot || err "boot_pool introuvable — vérifiez les pools ZFS"
info "boot_pool -> $BOOT"

# =============================================================================
# TYPE D'INIT
# =============================================================================
if [[ -z "${INIT_TYPE:-}" ]]; then
    echo ""
    echo -e "  ${BOLD}Type d'initramfs a construire${NC}"
    echo "  1) zbm        - Init complet : overlay + pivot_root + Python TUI"
    echo "  2) zbm-stream - Variante stream seule, sans TUI"
    echo "  3) minimal    - Init natif noyau (necessite dracut + kver cible)"
    echo "  4) custom-<n> - Init personnalise"
    echo -n "  Choix [1/2/3/4] : "
    read -r CHOICE
    case "$CHOICE" in
        1) INIT_TYPE="zbm" ;;
        2) INIT_TYPE="zbm-stream" ;;
        3) INIT_TYPE="minimal" ;;
        4) echo -n "  Nom (ex: custom-hibernate) : "; read -r INIT_TYPE ;;
        *) err "Choix invalide" ;;
    esac
fi

INIT_LABEL="${INIT_TYPE}"
INITRAMFS_DST=$(zbm_path initramfs "" "$INIT_LABEL" "$TODAY")
mkdir -p "$(zbm_dir initramfs)"

echo ""
echo "  Type     : $INIT_TYPE"
echo "  Cible    : $INITRAMFS_DST"

if [[ -f "$INITRAMFS_DST" ]]; then
    warn "$(basename "$INITRAMFS_DST") existe deja"
    echo -n "  Ecraser ? [o/N] : "
    read -r CONFIRM
    [[ "$CONFIRM" =~ ^[Oo]$ ]] || { ok "Annule"; exit 0; }
fi

# =============================================================================
# CAS SPECIAL : minimal = init natif noyau, dracut REQUIS avec kver cible
# =============================================================================
if [[ "$INIT_TYPE" == "minimal" ]]; then
    command -v dracut >/dev/null || err "dracut non installe (requis pour type minimal)"

    # Sélection du kernel cible pour dracut (type minimal uniquement)
    # Afficher la liste des kernels installés dans boot_pool pour choisir
    KVER_AUTO=""
    echo ""
    echo "  Sélectionner le kernel cible (kver requis par dracut) :"
    _SEL_K=$(zbm_select_kernel --quiet) || true
    if [[ -n "$_SEL_K" ]]; then
        IFS='|' read -r _KP _KL _KD KVER_AUTO <<< "$_SEL_K"
        [[ "$KVER_AUTO" == "?" ]] && KVER_AUTO=""
        if [[ -n "$KVER_AUTO" ]]; then
            ok "Kernel sélectionné : kernel-${_KL}-${_KD}  kver=${KVER_AUTO}"
        else
            warn "Kernel trouvé mais kver inconnue dans les .meta"
        fi
    fi

    # Fallback : lecture directe depuis config.sh
    [[ -z "$KVER_AUTO" ]] && KVER_AUTO="${KERNEL_VER:-}"

    if [[ -z "$KVER_AUTO" ]]; then
        warn "Aucun kernel trouvé dans boot_pool ou kver manquante."
        echo "  Installez d'abord un kernel avec lib/kernel.sh"
        echo "  Ou afficher la liste :"
        zbm_select_kernel 2>/dev/null || true
        echo ""
        echo -n "  Saisir la kver manuellement (ex: 6.12.0-4-amd64) : "
        read -r KVER_AUTO
    fi
    [[ -n "$KVER_AUTO" ]] || err "kver requise pour type minimal"

    echo ""
    info "Init minimal, dracut, kver=$KVER_AUTO"
    warn "Ceci necessite que /lib/modules/$KVER_AUTO existe sur le systeme courant."
    [[ -d "/lib/modules/$KVER_AUTO" ]] \
        || err "Modules absents : /lib/modules/$KVER_AUTO -- type minimal impossible depuis ce live"

    DRACUT_CONF=$(mktemp /tmp/zbm-dracut-XXXX.conf)
    cat > "$DRACUT_CONF" << DCONF
add_dracutmodules+=" kernel-modules base "
omit_dracutmodules+=" nfs iscsi multipath biosdevname systemd "
add_drivers+=" zfs squashfs overlay e1000e i915 loop "
compress="zstd"
DCONF
    dracut --conf "$DRACUT_CONF" --force --no-hostonly \
        --kver "$KVER_AUTO" "$INITRAMFS_DST" 2>&1 | tail -5 | sed 's/^/  /'
    rm -f "$DRACUT_CONF"
    chmod 444 "$INITRAMFS_DST"
    ok "$(basename "$INITRAMFS_DST")  ($(du -sh "$INITRAMFS_DST" | cut -f1))"
    zbm_write_meta "$INITRAMFS_DST" "init_type=minimal" "kernel_ver=${KVER_AUTO}" "builder=initramfs.sh"
    exit 0
fi

# =============================================================================
# CAS PRINCIPAL : zbm / zbm-stream / custom-<n>
# Construction directe du cpio — AUCUNE dependance a la version du kernel
# Les modules viennent de modules.sfs au boot, pas de l'initramfs
# =============================================================================

# Selectionner le fichier init source
case "$INIT_TYPE" in
    zbm-stream)
        [[ -f "$INIT_STREAM_SRC" ]] || err "initramfs-stream-init introuvable : $INIT_STREAM_SRC"
        INIT_FILE="$INIT_STREAM_SRC"
        ;;
    zbm)
        [[ -f "$INIT_SRC" ]] || err "initramfs-init introuvable : $INIT_SRC"
        INIT_FILE="$INIT_SRC"
        ;;
    custom-*)
        CUSTOM_INIT="$PROJECT_ROOT/${INIT_TYPE}-init"
        [[ -f "$CUSTOM_INIT" ]] || err "Init custom introuvable : $CUSTOM_INIT"
        INIT_FILE="$CUSTOM_INIT"
        ;;
    *)
        err "Type d'init inconnu : $INIT_TYPE"
        ;;
esac

info "Init source : $INIT_FILE"
echo ""
echo "  Construction du cpio (sans dracut, sans kernel version)..."

# ----- Répertoire de travail -----
INJECT=$(mktemp -d /tmp/initramfs-build-XXXX)

# ----- Structure de base -----
mkdir -p \
    "$INJECT/bin"        \
    "$INJECT/sbin"       \
    "$INJECT/usr/bin"    \
    "$INJECT/usr/sbin"   \
    "$INJECT/lib"        \
    "$INJECT/lib64"      \
    "$INJECT/lib/x86_64-linux-gnu" \
    "$INJECT/proc"       \
    "$INJECT/sys"        \
    "$INJECT/dev"        \
    "$INJECT/run"        \
    "$INJECT/tmp"        \
    "$INJECT/mnt/boot"   \
    "$INJECT/mnt/lower"  \
    "$INJECT/mnt/fast"   \
    "$INJECT/mnt/merged" \
    "$INJECT/mnt/modloop"\
    "$INJECT/mnt/python" \
    "$INJECT/mnt/work"   \
    "$INJECT/mnt/tmp"

# ----- /init -----
cp "$INIT_FILE" "$INJECT/init"
chmod 755 "$INJECT/init"
info "/init installe"

# ----- Fonction : copier un binaire + toutes ses libs partagées -----
copy_bin() {
    local bin_path="$1"
    local dst_dir="${2:-$INJECT/bin}"
    [[ -f "$bin_path" ]] || { warn "Binaire absent : $bin_path"; return 1; }
    mkdir -p "$dst_dir"
    cp -f "$bin_path" "$dst_dir/$(basename "$bin_path")"

    # Copier les libs (ldd)
    ldd "$bin_path" 2>/dev/null | awk '
        /=> \// { print $3 }
        /^[[:space:]]*\// { print $1 }
    ' | sort -u | while read -r lib; do
        [[ -f "$lib" ]] || continue
        lib_dir="$INJECT$(dirname "$lib")"
        mkdir -p "$lib_dir"
        cp -f "$lib" "$lib_dir/" 2>/dev/null || true
        # Résoudre les liens symboliques
        if [[ -L "$lib" ]]; then
            real_lib=$(readlink -f "$lib")
            [[ -f "$real_lib" ]] && cp -f "$real_lib" "$lib_dir/" 2>/dev/null || true
        fi
    done
}

# ----- Binaires requis -----
echo "  Copie des binaires requis..."

# Préférer busybox si disponible (embarque mount, umount, modprobe, etc.)
BUSYBOX_BIN=$(command -v busybox 2>/dev/null || true)
if [[ -n "$BUSYBOX_BIN" ]]; then
    copy_bin "$BUSYBOX_BIN" "$INJECT/bin"
    # Créer les liens symboliques pour les applets busybox utilisées par notre init
    for applet in sh ash mount umount mkdir sleep cat echo ln cp modprobe insmod depmod; do
        [[ -e "$INJECT/bin/$applet" ]] || ln -sf busybox "$INJECT/bin/$applet"
    done
    info "busybox installe + applets"
else
    # Pas de busybox — copier les binaires individuellement
    warn "busybox absent -- copie binaires individuels (plus grand)"
    for bin in sh bash mount umount mkdir sleep cat ln cp; do
        BIN_PATH=$(command -v "$bin" 2>/dev/null || true)
        [[ -n "$BIN_PATH" ]] && copy_bin "$BIN_PATH"
    done
    for bin in modprobe insmod depmod; do
        BIN_PATH=$(command -v "$bin" 2>/dev/null || true)
        [[ -n "$BIN_PATH" ]] && copy_bin "$BIN_PATH" "$INJECT/sbin"
    done
fi

# Binaires spécifiques ZFS et montage — toujours copier explicitement
for bin in zfs zpool; do
    BIN_PATH=$(command -v "$bin" 2>/dev/null || true)
    [[ -z "$BIN_PATH" ]] && { warn "$bin absent du live"; continue; }
    copy_bin "$BIN_PATH" "$INJECT/sbin"
done

# mountpoint (utilisé pour les guards anti-double-montage)
BIN_PATH=$(command -v mountpoint 2>/dev/null || true)
[[ -n "$BIN_PATH" ]] && copy_bin "$BIN_PATH" "$INJECT/bin" || warn "mountpoint absent"

# pivot_root et switch_root
for bin in pivot_root switch_root; do
    BIN_PATH=$(command -v "$bin" 2>/dev/null || true)
    if [[ -n "$BIN_PATH" ]]; then
        copy_bin "$BIN_PATH" "$INJECT/sbin"
    else
        # Peut être dans /usr/sbin ou embarqué dans util-linux
        for d in /sbin /usr/sbin /bin /usr/bin; do
            [[ -f "$d/$bin" ]] && { copy_bin "$d/$bin" "$INJECT/sbin"; break; }
        done
    fi
done

# ld-linux (l'éditeur de liens dynamiques) — indispensable
for ld in /lib64/ld-linux-x86-64.so.2 /lib/x86_64-linux-gnu/ld-linux-x86-64.so.2; do
    if [[ -f "$ld" ]]; then
        mkdir -p "$INJECT$(dirname "$ld")"
        cp -f "$ld" "$INJECT$(dirname "$ld")/"
        break
    fi
done

# Liens symboliques de compatibilité
[[ -e "$INJECT/sbin/init" ]] || ln -sf /init "$INJECT/sbin/init" 2>/dev/null || true
[[ -d "$INJECT/usr/bin" ]] && ln -sf /bin/sh "$INJECT/usr/bin/sh" 2>/dev/null || true

# Créer /dev/console et /dev/null minimaux (nœuds de device)
# (le kernel les crée aussi, mais avoir les entrées dans le cpio est plus propre)
mkdir -p "$INJECT/dev"
# Note : mknod nécessite root — on s'en passe, le kernel initialisera /dev via devtmpfs

info "Binaires copies"

# ----- Résumé du contenu -----
INJECT_SIZE=$(du -sh "$INJECT" | cut -f1)
echo "  Taille repertoire staging : $INJECT_SIZE"

# ----- Packaging cpio + zstd -----
echo "  Packaging cpio + zstd..."
(
    cd "$INJECT"
    find . | sort | cpio -o -H newc --quiet 2>/dev/null
) | zstd -5 -q > "$INITRAMFS_DST"
chmod 444 "$INITRAMFS_DST"

FINAL_SIZE=$(du -sh "$INITRAMFS_DST" | cut -f1)
ok "$(basename "$INITRAMFS_DST")  ($FINAL_SIZE)"

# ----- Meta : kver depuis le kernel installe en boot_pool -----
KVER_META=""
for mf in "$(zbm_dir kernel)"/kernel-*.meta; do
    [[ -f "$mf" ]] || continue
    KVER_META=$(zbm_read_meta "${mf%.meta}" "kernel_ver" 2>/dev/null || true)
    [[ -n "$KVER_META" ]] && break
done

zbm_write_meta "$INITRAMFS_DST" \
    "init_type=${INIT_TYPE}" \
    "kernel_ver=${KVER_META:-independent}" \
    "builder=initramfs.sh"
ok "Sidecar .meta"

# ----- Résumé -----
echo ""
echo "  Initramfs disponibles dans boot_pool :"
for f in "$(zbm_dir initramfs)"/initramfs-*; do
    [[ -f "$f" ]] && [[ "$f" != *.meta ]] || continue
    it=$(zbm_read_meta "$f" "init_type" 2>/dev/null || true)
    printf "    %-44s  type=%s  %s\n" "$(basename "$f")" "${it:-?}" "$(du -sh "$f" | cut -f1)"
done

echo ""
echo -e "  ${CYAN}Prochaine etape : lib/presets.sh${NC}"
