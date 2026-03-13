#!/bin/bash
# =============================================================================
# create-failsafe.sh — Création du failsafe figé
#
# Usage  : ./create-failsafe.sh <system> <label> [<date_source>]
# Exemple: ./create-failsafe.sh systeme1 gentoo-6.19
#          ./create-failsafe.sh systeme1 gentoo-6.19 20250305
#
# Copie un ensemble d'images existant vers /boot/images/failsafe/
# en renommant avec system=failsafe selon la convention :
#
#   Source                                      Destination
#   ────────────────────────────────────────    ──────────────────────────────────────────
#   images/kernels/kernel-<label>-<date>        images/failsafe/kernel-failsafe-<label>-<date>
#   images/initramfs/initramfs-<init>-<date>.img images/failsafe/initramfs-failsafe-<init>-<date>.img
#   images/modules/modules-<label>-<date>.sfs   images/failsafe/modules-failsafe-<label>-<date>.sfs
#   images/rootfs/rootfs-<s>-<label>-<date>.sfs images/failsafe/rootfs-failsafe-<label>-<date>.sfs
#
# NOTE : kernel/initramfs/modules sont INDÉPENDANTS des systèmes.
#        Le champ "system" est retiré pour ces types.
#        Seul le rootfs garde son champ "system" → "failsafe".
#
# RÈGLES ABSOLUES :
#   - Script MANUEL uniquement — jamais appelé par l'UI
#   - L'UI Python ne touche JAMAIS à /boot/images/failsafe/
#   - Le preset failsafe.json est protected:true
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# naming.sh est dans lib/ si lancé depuis la racine, ou dans le même répertoire
for candidate in "$SCRIPT_DIR/lib/naming.sh" "$SCRIPT_DIR/naming.sh"; do
    [[ -f "$candidate" ]] && { source "$candidate"; break; }
done
type zbm_stem &>/dev/null || { echo "naming.sh introuvable"; exit 1; }

RED='\033[1;31m'; GREEN='\033[1;32m'; YELLOW='\033[1;33m'
BLUE='\033[1;34m'; CYAN='\033[1;36m'; BOLD='\033[1m'; NC='\033[0m'
ok()   { echo -e "  ${GREEN}✅ $*${NC}"; }
warn() { echo -e "  ${YELLOW}⚠️  $*${NC}"; }
err()  { echo -e "  ${RED}❌ $*${NC}"; exit 1; }
step() { echo -e "\n${BLUE}${BOLD}▶ $*${NC}"; }

usage() {
    echo "Usage: $0 <system> <label> [<date>]"
    echo "  system : systeme1 | systeme2"
    echo "  label  : ex. gentoo-6.19"
    echo "  date   : YYYYMMDD (défaut : ensemble le plus récent)"
    exit 1
}

[[ $EUID -ne 0 ]] && err "Root requis"
[[ $# -lt 2 ]] && usage

SRC_SYSTEM="$1"
LABEL="$2"
SRC_DATE="${3:-}"
# Localisation dynamique de boot_pool
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
PRESETS_DIR="$BOOT/presets"

# =============================================================================
# TROUVER L'ENSEMBLE SOURCE
# =============================================================================
step "Recherche de l'ensemble source"

if [[ -z "$SRC_DATE" ]]; then
    # Prendre le plus récent
    SRC_DATE=""
    # Kernels : nommage kernel-<label>-<date> (PAS de champ system)
    for f in "$(zbm_dir kernel)"/kernel-*-????????; do
        [[ -f "$f" ]] && [[ "$f" != *.meta ]] || continue
        eval "$(zbm_parse "$f")" || continue
        [[ "$ZBM_LABEL" == "$LABEL" ]] && SRC_DATE="$ZBM_DATE"
    done
    [[ -n "$SRC_DATE" ]] || err "Aucun ensemble trouvé pour ${SRC_SYSTEM}/${LABEL}"
    echo "  Date sélectionnée : $SRC_DATE (le plus récent)"
fi

# Vérifier que l'ensemble source est complet
# zbm_set_complete prend (kernel_label date) — kernel indépendant du system
zbm_set_complete "$LABEL" "$SRC_DATE" \
    || err "Ensemble source incomplet : ${LABEL}/${SRC_DATE}"

SRC_K=$(zbm_path kernel    "" "$LABEL" "$SRC_DATE")  # kernel : pas de system dans le nom
# BUG 5 FIX : l'initramfs a pour label le TYPE D'INIT (zbm, zbm-stream...)
# et NON le label du kernel — on cherche par date parmi les initramfs disponibles
SRC_I=$(ls "$(zbm_dir initramfs)"/initramfs-*-"${SRC_DATE}.img" 2>/dev/null \
    | grep -v '\.meta$' | sort | tail -1 || true)
[[ -n "$SRC_I" && -f "$SRC_I" ]] \
    || err "Aucun initramfs trouvé pour la date $SRC_DATE dans $(zbm_dir initramfs)"
# Extraire le label de l'initramfs source (ex: "zbm" depuis initramfs-zbm-20250305.img)
INIT_LABEL=$(basename "$SRC_I" .img | sed "s/^initramfs-//;s/-${SRC_DATE}$//")
SRC_M=$(zbm_path modules   "" "$LABEL" "$SRC_DATE")  # modules  : pas de system
SRC_R=$(zbm_path rootfs    "$SRC_SYSTEM" "$LABEL" "$SRC_DATE")

echo "  Source : ${SRC_SYSTEM}/${LABEL}/${SRC_DATE}  (init=${INIT_LABEL})"
for f in "$SRC_K" "$SRC_I" "$SRC_M" "$SRC_R"; do
    ok "$(basename "$f")  ($(du -sh "$f" | cut -f1))"
done

# Date du failsafe = date du jour (création d'un nouveau snapshot figé)
FS_DATE=$(date +%Y%m%d)
FS_DIR="$(zbm_dir failsafe)"

DST_K=$(zbm_path kernel    failsafe "$LABEL"      "$FS_DATE")
DST_I=$(zbm_path initramfs failsafe "$INIT_LABEL" "$FS_DATE")  # label = type d'init
DST_M=$(zbm_path modules   failsafe "$LABEL"      "$FS_DATE")
DST_R=$(zbm_path rootfs    failsafe "$LABEL"      "$FS_DATE")
DST_META="$FS_DIR/failsafe-${LABEL}-${FS_DATE}.meta"
PRESET="$PRESETS_DIR/failsafe.json"

# =============================================================================
# GESTION DE L'EXISTANT
# =============================================================================
if ls "$FS_DIR"/kernel-failsafe-* >/dev/null 2>&1; then
    step "Failsafe existant détecté"
    ls "$FS_DIR"/ | sed 's/^/    /'
    echo ""
    echo -e "  ${YELLOW}Un failsafe existant sera sauvegardé.${NC}"
    echo -n "  Continuer ? [o/N] : "
    read -r CONFIRM
    [[ "$CONFIRM" =~ ^[Oo]$ ]] || { echo "Annulé."; exit 0; }
    BACKUP="${FS_DIR}.bak.$(date +%Y%m%d-%H%M%S)"
    mv "$FS_DIR" "$BACKUP"
    echo "  Sauvegarde → $(basename "$BACKUP")"
fi

mkdir -p "$FS_DIR" "$PRESETS_DIR"

# =============================================================================
# COPIE VÉRIFIÉE
# =============================================================================
step "Copie et vérification MD5"

copy_verified() {
    local src="$1" dst="$2"
    echo -n "  $(basename "$dst")... " >&2
    cp "$src" "$dst"
    local md5_src md5_dst
    md5_src=$(md5sum "$src" | awk '{print $1}')
    md5_dst=$(md5sum "$dst" | awk '{print $1}')
    [[ "$md5_src" == "$md5_dst" ]] || { echo "ERREUR MD5" >&2; rm -rf "$FS_DIR"; exit 1; }
    chmod 444 "$dst"
    echo -e "${GREEN}OK  ($(du -sh "$dst" | cut -f1))${NC}" >&2
    echo "$md5_src"
}

MD5_K=$(copy_verified "$SRC_K" "$DST_K")
MD5_I=$(copy_verified "$SRC_I" "$DST_I")
MD5_M=$(copy_verified "$SRC_M" "$DST_M")
MD5_R=$(copy_verified "$SRC_R" "$DST_R")

# =============================================================================
# MÉTADONNÉES
# =============================================================================
step "Écriture des métadonnées"

cat > "$DST_META" << META
# failsafe.meta — GÉNÉRÉ AUTOMATIQUEMENT — NE PAS MODIFIER
date=$(date -Iseconds)
src_system=${SRC_SYSTEM}
src_date=${SRC_DATE}
fs_date=${FS_DATE}
label=${LABEL}
hostname=$(hostname)
total=$(du -sh "$FS_DIR" | cut -f1)
overlay_dataset=fast_pool/overlay-failsafe
# var_dataset / log_dataset supprimés (architecture overlay)
md5_kernel=${MD5_K}
md5_initramfs=${MD5_I}
md5_modules=${MD5_M}
md5_rootfs=${MD5_R}
META
ok "$(basename "$DST_META")"

# =============================================================================
# PRESET ZFSBOOTMENU
# =============================================================================
step "Écriture failsafe.json"

# BUG 7 FIX : les chemins dans la cmdline doivent être RELATIFS à boot_pool
# (initramfs-init appelle resolve_boot_path() qui préfixe /mnt/boot)
# Les chemins absolus contiennent /mnt/zbm-live/... qui n'existe pas au boot réel
DST_R_REL="${DST_R#${BOOT}/}"
DST_M_REL="${DST_M#${BOOT}/}"

cat > "${PRESET}.tmp" << JSON
{
    "_comment": "Géré UNIQUEMENT par create-failsafe.sh. NE PAS MODIFIER.",
    "_generated": "$(date -Iseconds)",
    "_image_set": "failsafe/${LABEL}/${FS_DATE}",
    "name": "failsafe",
    "label": "⛑  Failsafe  [${LABEL} / ${FS_DATE} ← ${SRC_SYSTEM}/${SRC_DATE}]",
    "priority": 999,
    "protected": true,
    "type": "prepared",
    "kernel":    "${DST_K}",
    "initramfs": "${DST_I}",
    "modules":   "${DST_M}",
    "rootfs":    "${DST_R}",
    "python_sfs": "",
    // var/log/tmp_dataset supprimés (architecture overlay)
    "overlay_dataset": "fast_pool/overlay-failsafe",
    "home_dataset":    "",
    "rootfs_label":    "${LABEL}",
    "stream_key":      "",
    "cmdline": "ro quiet loglevel=3 zbm_system=failsafe zbm_rootfs=${DST_R_REL} zbm_modules=${DST_M_REL} zbm_overlay=fast_pool/overlay-failsafe"
}
JSON
mv "${PRESET}.tmp" "$PRESET"
ok "failsafe.json  (priority:999, protected:true)"

# =============================================================================
# SYMLINKS FAILSAFE
# =============================================================================
step "Symlinks failsafe dans $BOOT/boot/"

# Les symlinks failsafe sont dans $BOOT/boot/ — ZBM cherche <BE>/boot/vmlinuz.failsafe
BOOT_LINKS_DIR="$BOOT/boot"
mkdir -p "$BOOT_LINKS_DIR"

while IFS='|' read -r link target_rel; do
    full_target="$BOOT/$target_rel"
    [[ -e "$full_target" ]] || { warn "cible manquante : $target_rel"; continue; }
    # Chemin relatif depuis $BOOT/boot/ vers la cible (ex: ../images/failsafe/...)
    rel=$(realpath --relative-to="$BOOT_LINKS_DIR" "$full_target" 2>/dev/null || echo "$target_rel")
    ln -sf "$rel" "$BOOT_LINKS_DIR/$link"
    ok "boot/$link → $rel"
done < <(zbm_failsafe_links "$LABEL" "$FS_DATE")

# =============================================================================
# RÉSUMÉ
# =============================================================================
echo ""
echo -e "${GREEN}${BOLD}╔══════════════════════════════════════════════════════════════╗"
echo            "║   ✅ FAILSAFE CRÉÉ                                           ║"
echo -e         "╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "  Source   : ${SRC_SYSTEM}/${LABEL}/${SRC_DATE}"
echo "  Failsafe : failsafe/${LABEL}/${FS_DATE}"
echo "  Taille   : $(du -sh "$FS_DIR" | cut -f1)"
echo ""
echo "  Fichiers :"
ls "$FS_DIR" | sed 's/^/    /'
echo ""
echo -e "  ${RED}Ce script est MANUEL uniquement.${NC}"
echo    "  L'UI ne peut PAS modifier $BOOT/images/failsafe/"
echo ""
