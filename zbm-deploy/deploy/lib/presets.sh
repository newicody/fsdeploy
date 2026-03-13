#!/bin/bash
# =============================================================================
# lib/presets.sh — Génération et gestion des presets de boot
#
# Un PRESET DE BOOT combine librement des composants INDÉPENDANTS :
#   kernel     kernel-<label>-<date>             (obligatoire)
#   initramfs  initramfs-<init_type>-<date>.img  (obligatoire)
#   modules    modules-<label>-<date>.sfs         (optionnel)
#   rootfs     rootfs-<s>-<label>-<date>.sfs  (optionnel selon init_type)
#
# TYPES DE PRESETS :
#
#   prepared   : kernel + initramfs zbm + modules + rootfs + python TUI + stream
#                Boot complet avec l'interface de configuration
#   normal     : kernel + initramfs zbm + modules + rootfs, sans stream
#                Boot système sans interface d'administration
#   stream     : kernel + initramfs zbm-stream + modules + rootfs
#                Boot optimisé flux vidéo, Python TUI non démarré
#   minimal    : kernel + initramfs minimal (init natif), rootfs optionnel
#                Boot brut, sans overlay ni Python
#   failsafe   : protected:true, géré par 06/update-failsafe-links.sh
#
# ÉTAT INITIAL (premier déploiement) :
#   On dispose uniquement d'un kernel générique + initramfs zbm minimal.
#   Aucun rootfs n'est requis pour ce preset initial.
#   Il permet de booter et d'utiliser l'interface Python pour configurer la suite.
#
# Usage : bash lib/presets.sh [--force] [--initial]
#   --force    : écraser les presets existants
#   --initial  : créer uniquement le preset initial (kernel générique, sans rootfs)
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/naming.sh"

GREEN='\033[1;32m'; YELLOW='\033[1;33m'; RED='\033[1;31m'
CYAN='\033[1;36m'; BOLD='\033[1m'; NC='\033[0m'
ok()   { echo -e "  ${GREEN}✅ $*${NC}"; }
warn() { echo -e "  ${YELLOW}⚠️  $*${NC}"; }
err()  { echo -e "  ${RED}❌ $*${NC}"; exit 1; }
info() { echo -e "  ${CYAN}   $*${NC}"; }

# Localisation de boot_pool — utilise zbm_locate_boot() de naming.sh
# Sur Debian live /boot est occupé → boot_pool monté sur ${ZBM_BOOT:-/mnt/zbm/boot}
_MOUNTED_BOOT=0  # rétrocompat
_cleanup_boot() { zbm_cleanup_boot; }
trap _cleanup_boot EXIT
zbm_locate_boot || err "boot_pool introuvable — vérifiez les pools ZFS"
info "boot_pool -> $BOOT"
PRESETS_DIR="$BOOT/presets"
HOOKS_DIR="$BOOT/hooks"
FORCE=0
INITIAL_ONLY=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --force)   FORCE=1;        shift ;;
        --initial) INITIAL_ONLY=1; shift ;;
        *) err "Argument inconnu : $1" ;;
    esac
done

mkdir -p "$PRESETS_DIR" "$HOOKS_DIR"

# Lire kernel_ver depuis un .meta
read_kver() { zbm_read_meta "$1" "kernel_ver" 2>/dev/null || true; }
read_init()  { zbm_read_meta "$1" "init_type"  2>/dev/null || true; }

# Sauvegarder un preset avec avertissement
write_preset() {
    local file="$1" json="$2"
    if [[ -f "$file" ]] && [[ $FORCE -eq 0 ]]; then
        warn "$(basename "$file") existe — conservé (--force pour écraser)"
        return 0
    fi
    if [[ -f "$file" ]]; then
        warn "Écrasement de $(basename "$file") — ancienne version sauvegardée"
        cp "$file" "${file}.bak.$(date +%Y%m%d%H%M%S)"
    fi
    echo "$json" > "$file"
    ok "$(basename "$file")"
}

# =============================================================================
# 1. PRESET INITIAL — kernel générique seul (pas de rootfs requis)
# =============================================================================
generate_initial() {
    echo -e "\n  ${BOLD}Preset initial (boot minimal sans rootfs)${NC}"

    # Trouver le kernel générique le plus récent
    local K_PATH="" K_LABEL="" K_DATE="" K_VER=""
    for f in "$(zbm_dir kernel)"/kernel-*; do
        [[ -f "$f" ]] && [[ "$f" != *.meta ]] || continue
        local p; p=$(zbm_parse "$f") || continue; eval "$p"
        [[ "$ZBM_SYSTEM" == "failsafe" ]] && continue
        # Préférer "generic" dans le label
        if [[ -z "$K_PATH" ]] || [[ "$ZBM_DATE" > "$K_DATE" ]] || \
           [[ "$ZBM_LABEL" == *generic* ]]; then
            K_PATH="$f"; K_LABEL="$ZBM_LABEL"; K_DATE="$ZBM_DATE"
            K_VER=$(read_kver "$f")
        fi
    done

    if [[ -z "$K_PATH" ]]; then
        warn "Aucun kernel trouvé — preset initial non généré"
        warn "Lancez d'abord : bash lib/kernel.sh --label generic-<version>"
        return 1
    fi

    # Initramfs zbm le plus récent
    local I_PATH="" I_LABEL="" I_DATE=""
    for f in "$(zbm_dir initramfs)"/initramfs-zbm-*.img; do
        [[ -f "$f" ]] && [[ "$f" != *.meta ]] || continue
        local p; p=$(zbm_parse "$f") || continue; eval "$p"
        [[ "$ZBM_LABEL" == "zbm" ]] || continue
        if [[ -z "$I_PATH" ]] || [[ "$ZBM_DATE" > "$I_DATE" ]]; then
            I_PATH="$f"; I_LABEL="$ZBM_LABEL"; I_DATE="$ZBM_DATE"
        fi
    done

    if [[ -z "$I_PATH" ]]; then
        warn "Aucun initramfs-zbm-*.img trouvé — preset initial non généré"
        warn "Lancez d'abord : bash lib/initramfs.sh  (choisir type zbm)"
        return 1
    fi

    # Modules pour ce kernel si disponibles
    local M_PATH="" M_LABEL=""
    local M_LATEST; M_LATEST=$(zbm_latest modules "" "$K_LABEL")
    [[ -f "${M_LATEST:-}" ]] && { M_PATH="$M_LATEST"; M_LABEL="$K_LABEL"; }

    local PRESET_FILE="$PRESETS_DIR/initial.json"
    local M_JSON="null"
    [[ -n "$M_PATH" ]] && M_JSON="\"${M_PATH}\""

    # Chemins RELATIFS à boot_pool (initramfs monte toujours boot_pool sur /mnt/boot)
    # Jamais de chemin absolu dépendant du live (/mnt/gentoo/boot/...)
    local INIT_CMDLINE="quiet loglevel=3 zbm_system=initial"
    if [[ -n "$M_JSON" ]] && [[ "$M_JSON" != "null" ]]; then
        local M_REL; M_REL=$(realpath --relative-to="$BOOT" "${M_LATEST:-}" 2>/dev/null             || echo "${M_LATEST#${BOOT}/}")
        INIT_CMDLINE+=" zbm_modules=${M_REL}"
    fi
    # Mode init-only : zbm_rootfs=none → pas d'overlay, pas de pivot_root
    INIT_CMDLINE+=" zbm_rootfs=none"
    # zbm_exec : python TUI si disponible, sinon shell (auto-détection dans init)

    local JSON
    JSON=$(cat << JSON
{
    "_generated":   "$(date -Iseconds)",
    "_description": "Preset init-only — boot sans rootfs, sans overlay",
    "_boot_mode":   "init-only",
    "name":         "initial",
    "label":        "Boot initial / Init-only (${K_LABEL})",
    "priority":     5,
    "protected":    false,
    "type":         "prepared",
    "init_type":    "zbm",
    "_kernel_ver":  "${K_VER}",
    "kernel":       "${K_PATH}",
    "initramfs":    "${I_PATH}",
    "modules":      ${M_JSON},
    "rootfs":       null,
    "exec":         "",
    "python_sfs":   null,
    "var_dataset":     null,
    "log_dataset":     null,
    "tmp_dataset":     null,
    "overlay_dataset": null,
    "home_dataset":    null,
    "stream_key":      "",
    "stream_resolution": "1920x1080",
    "stream_fps":        30,
    "stream_bitrate":    "4500k",
    "stream_delay_sec":  30,
    "network_mode":  "dhcp",
    "network_iface": "auto",
    "cmdline": "${INIT_CMDLINE}"
}
JSON
)
    write_preset "$PRESET_FILE" "$JSON"
    ok "Preset initial : kernel=${K_LABEL} | init=zbm | rootfs=aucun"
    warn "Ce preset boot sur un shell minimal via Python TUI"
    warn "Utilisez l'UI pour ajouter un rootfs et basculer vers un preset complet"
}

# =============================================================================
# 2. PRESETS COMPLETS — pour chaque combinaison kernel + initramfs + rootfs
# =============================================================================
generate_full() {
    echo -e "\n  ${BOLD}Découverte des composants disponibles${NC}"

    # Python SFS le plus récent
    local PYTHON_SFS
    PYTHON_SFS=$(ls "$(zbm_dir python)"/python-*.sfs 2>/dev/null | grep -v '\.meta$' | sort | tail -1 || true)

    # Lister les rootfs disponibles
    local -a ROOTFS_LIST=()
    while IFS=' ' read -r rsys rlbl rdt; do
        ROOTFS_LIST+=("${rsys}|${rlbl}|${rdt}")
    done < <(zbm_list_rootfs)

    if [[ ${#ROOTFS_LIST[@]} -eq 0 ]]; then
        warn "Aucun rootfs disponible — seul le preset initial peut être généré"
        return 0
    fi

    # Pour chaque rootfs, chercher le meilleur kernel + initramfs zbm
    local PRIORITY=10

    for rf_entry in "${ROOTFS_LIST[@]}"; do
        IFS='|' read -r RSYS RLBL RDT <<< "$rf_entry"
        local R_PATH; R_PATH=$(zbm_path rootfs "$RSYS" "$RLBL" "$RDT")

        # Trouver le kernel le plus récent
        local K_PATH="" K_LABEL="" K_DATE="" K_VER=""
        for f in "$(zbm_dir kernel)"/kernel-*; do
            [[ -f "$f" ]] && [[ "$f" != *.meta ]] || continue
            local p; p=$(zbm_parse "$f") || continue; eval "$p"
            [[ "$ZBM_SYSTEM" == "failsafe" ]] && continue
            if [[ -z "$K_PATH" ]] || [[ "$ZBM_DATE" > "$K_DATE" ]]; then
                K_PATH="$f"; K_LABEL="$ZBM_LABEL"; K_DATE="$ZBM_DATE"
                K_VER=$(read_kver "$f")
            fi
        done
        [[ -z "$K_PATH" ]] && { warn "Aucun kernel — preset ${RSYS}/${RLBL} ignoré"; continue; }

        # Initramfs zbm le plus récent
        local I_PATH="" I_DATE=""
        for f in "$(zbm_dir initramfs)"/initramfs-zbm-*.img; do
            [[ -f "$f" ]] && [[ "$f" != *.meta ]] || continue
            local p; p=$(zbm_parse "$f") || continue; eval "$p"
            [[ "$ZBM_LABEL" == "zbm" ]] || continue
            if [[ -z "$I_PATH" ]] || [[ "$ZBM_DATE" > "$I_DATE" ]]; then
                I_PATH="$f"; I_DATE="$ZBM_DATE"
            fi
        done
        [[ -z "$I_PATH" ]] && { warn "Aucun initramfs-zbm — preset ${RSYS}/${RLBL} ignoré"; continue; }

        # Modules pour ce kernel
        local M_PATH="null"
        local M_LATEST; M_LATEST=$(zbm_latest modules "" "$K_LABEL" 2>/dev/null || true)
        [[ -f "${M_LATEST:-}" ]] && M_PATH="\"${M_LATEST}\""

        # Python SFS
        local PY_JSON="null"
        [[ -n "${PYTHON_SFS:-}" ]] && [[ -f "$PYTHON_SFS" ]] && PY_JSON="\"${PYTHON_SFS}\""

        # Type de preset
        local PTYPE="normal"
        [[ "$RSYS" == "systeme1" ]] && [[ -n "${PYTHON_SFS:-}" ]] && PTYPE="prepared"

        # Cmdline
        # Chemins RELATIFS à boot_pool (jamais de chemin absolu du live)
        local R_REL; R_REL=$(realpath --relative-to="$BOOT" "$R_PATH" 2>/dev/null \
            || echo "${R_PATH#${BOOT}/}")
        local CMDLINE="quiet loglevel=3 zbm_system=${RSYS} zbm_rootfs=${R_REL}"
        if [[ "$M_PATH" != "null" ]]; then
            local M_REL2; M_REL2=$(realpath --relative-to="$BOOT" "${M_LATEST:-}" 2>/dev/null \
                || echo "${M_LATEST#${BOOT}/}")
            CMDLINE+=" zbm_modules=${M_REL2}"
        fi
        CMDLINE+=" zbm_overlay=fast_pool/overlay-${RSYS}"  # var/log/tmp supprimés : architecture overlay

        local PRESET_FILE="$PRESETS_DIR/${RSYS}.json"

        local JSON
        JSON=$(cat << JSON
{
    "_generated":   "$(date -Iseconds)",
    "_image_set":   "${RSYS}/${RLBL}/${RDT}",
    "_kernel_ver":  "${K_VER}",
    "name":         "${RSYS}",
    "label":        "$(echo "$RSYS" | sed 's/systeme/Système /') — ${RLBL} [${PTYPE}]",
    "priority":     ${PRIORITY},
    "protected":    false,
    "type":         "${PTYPE}",
    "init_type":    "zbm",
    "kernel":       "${K_PATH}",
    "initramfs":    "${I_PATH}",
    "modules":      ${M_PATH},
    "rootfs":       "${R_PATH}",
    "python_sfs":   ${PY_JSON},
    "rootfs_label": "${RLBL}",
    "overlay_dataset": "fast_pool/overlay-${RSYS}",
    // var/log/tmp_dataset supprimés (architecture overlay)
    "home_dataset":    "data_pool/home",
    "stream_key":      "${STREAM_KEY:-}",
    "stream_resolution": "1920x1080",
    "stream_fps":        30,
    "stream_bitrate":    "4500k",
    "stream_delay_sec":  30,
    "network_mode":  "dhcp",
    "network_iface": "auto",
    "cmdline": "${CMDLINE}"
}
JSON
)
        write_preset "$PRESET_FILE" "$JSON"
        PRIORITY=$((PRIORITY + 10))
    done
}

# =============================================================================
# 3. HOOK ZBM POUR PRESETS NORMAUX
# =============================================================================
generate_hook() {
    # Note: Ce hook est exécuté dans l'environnement ZFSBootMenu (avant kexec).
    # Le système réel est monté par initramfs-init après kexec.
    # Ce hook se limite à préparer les datasets critiques si nécessaire.
    cat > "$HOOKS_DIR/zbm-hook-normal.sh" << 'HOOK'
#!/bin/sh
# Exécuté par ZFSBootMenu AVANT kexec — préparation minimale
# Le système lu depuis la cmdline kernel (zbm_system=)
ZBM_SYSTEM=$(tr ' ' '
' < /proc/cmdline | grep '^zbm_system=' | cut -d= -f2)
ZBM_SYSTEM="${ZBM_SYSTEM:-systeme1}"
# Montage explicite avec guard anti-double-montage
_mount_ds() {
    local ds="$1" mp="$2"
    zfs list "$ds" >/dev/null 2>&1 || return 0
    mountpoint -q "$mp" 2>/dev/null && return 0
    mkdir -p "$mp"
    mount -t zfs "$ds" "$mp" 2>/dev/null || true
}
_mount_ds "fast_pool/overlay-${ZBM_SYSTEM}" "/mnt/zbm-ovl"
# fast_pool/var-${ZBM_SYSTEM} supprimé : architecture overlay
HOOK
    chmod +x "$HOOKS_DIR/zbm-hook-normal.sh"
    ok "zbm-hook-normal.sh"
}

# =============================================================================
# 4. SYMLINKS ACTIFS VERS LE PRESET PRIORITAIRE
# =============================================================================
update_symlinks() {
    echo ""
    echo "  Mise à jour des symlinks $BOOT/boot/ ..."
    # Lire le preset à plus haute priorité (plus petit numéro)
    local best_preset="" best_prio=999
    for f in "$PRESETS_DIR"/*.json; do
        [[ -f "$f" ]] || continue
        local name prio prot
        name=$(python3 -c "import json; d=json.load(open('$f')); print(d.get('name',''))" 2>/dev/null || true)
        prot=$(python3 -c "import json; d=json.load(open('$f')); print(d.get('protected', False))" 2>/dev/null || true)
        # python3 imprime "True" ou "False" (capital) pour les booléens JSON
        [[ "$prot" == "True" ]] && continue
        prio=$(python3 -c "import json; d=json.load(open('$f')); print(d.get('priority',999))" 2>/dev/null || echo 999)
        [[ $prio -lt $best_prio ]] && { best_prio=$prio; best_preset="$f"; }
    done
    [[ -z "$best_preset" ]] && return

    local K I M R
    K=$(python3 -c "import json; d=json.load(open('$best_preset')); print(d.get('kernel','') or '')" 2>/dev/null || true)
    I=$(python3 -c "import json; d=json.load(open('$best_preset')); print(d.get('initramfs','') or '')" 2>/dev/null || true)
    M=$(python3 -c "import json; d=json.load(open('$best_preset')); v=d.get('modules'); print(v if v else '')" 2>/dev/null || true)
    R=$(python3 -c "import json; d=json.load(open('$best_preset')); v=d.get('rootfs'); print(v if v else '')" 2>/dev/null || true)

    # Symlinks dans $BOOT/boot/ — ZBM monte boot_pool comme BE et cherche
    # <BE_root>/boot/vmlinuz. boot_pool étant le BE : symlinks dans boot_pool/boot/.
    # Chemins RELATIFS : portables si boot_pool est remonté ailleurs.
    local BOOT_DIR="$BOOT/boot"
    mkdir -p "$BOOT_DIR"

    _mk_link() {
        local name="$1" src="$2"
        [[ -n "$src" && -f "$src" ]] || return 0
        local rel
        rel=$(realpath --relative-to="$BOOT_DIR" "$src" 2>/dev/null || echo "$src")
        ln -sf "$rel" "$BOOT_DIR/$name"             && ok "$BOOT_DIR/$name → $rel"
    }
    # Kernel + initramfs : requis
    _mk_link "vmlinuz"    "$K"
    _mk_link "initrd.img" "$I"
    # Modules + rootfs : optionnels
    [[ -n "$M" ]] && _mk_link "modules.sfs" "$M" || rm -f "$BOOT_DIR/modules.sfs"
    [[ -n "$R" ]] && _mk_link "rootfs.sfs"  "$R" || rm -f "$BOOT_DIR/rootfs.sfs"
}

# =============================================================================
# EXÉCUTION
# =============================================================================
echo -e "\n${BOLD}═══ Génération des presets de boot ═══${NC}"

generate_initial || warn "Preset initial non généré (kernel ou initramfs manquant)"
[[ $INITIAL_ONLY -eq 0 ]] && generate_full
generate_hook
update_symlinks

echo ""
echo "  Presets générés :"
for f in "$PRESETS_DIR"/*.json; do
    [[ -f "$f" ]] || continue
    NAME=$(python3 -c "import json; d=json.load(open('$f')); print(d.get('label','?'))" 2>/dev/null || basename "$f")
    TYPE=$(python3 -c "import json; d=json.load(open('$f')); print(d.get('type','?'))" 2>/dev/null || echo "?")
    INIT=$(python3 -c "import json; d=json.load(open('$f')); print(d.get('init_type','?'))" 2>/dev/null || echo "?")
    printf "    %-50s  [%s / init:%s]\n" "$NAME" "$TYPE" "$INIT"
done

echo ""
echo -e "  ${CYAN}Prochaine étape : bash lib/zbm.sh${NC}"
