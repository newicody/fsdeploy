#!/bin/bash
# =============================================================================
# lib/coherence.sh — Vérification de cohérence du système ZBM
#
# Trois niveaux :
#   A. Nommage    — fichiers dans /boot/images/ conformes à la convention
#   B. Presets    — kernel/initramfs/modules/rootfs existent, init_type cohérent
#   C. ZFS        — datasets mountpoints conformes à l'architecture canonique
#
# RAPPEL ARCHITECTURAL :
#   kernel / initramfs / modules → INDÉPENDANTS des rootfs
#   rootfs → PAS de kernel ni de modules dedans (scanné mais ignoré)
#   preset initial → rootfs=null, valide
#
# Usage :
#   bash lib/coherence.sh [OPTIONS]
#   --altroot /mnt/zbm   Préfixe zpool live CD (= ZBM_ALTROOT)
#   --fix                Corriger automatiquement
#   --dry-run            Voir les corrections sans les appliquer
#   --preset <n>         Filtrer un preset
#   --json               Sortie JSON pour l'UI Python
# =============================================================================

set -euo pipefail

_MOUNTS_SH="$(dirname "${BASH_SOURCE[0]}")/mounts.sh"
[[ -f "$_MOUNTS_SH" ]] && source "$_MOUNTS_SH"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/naming.sh"

GREEN='\033[1;32m'; YELLOW='\033[1;33m'; RED='\033[1;31m'
CYAN='\033[1;36m'; BOLD='\033[1m'; DIM='\033[2m'; NC='\033[0m'
ok()     { echo -e "  ${GREEN}✅${NC} $*"; }
warn()   { echo -e "  ${YELLOW}⚠️ ${NC} $*"; }
err_ln() { echo -e "  ${RED}❌${NC} $*"; }
fix_ln() { echo -e "  ${CYAN}🔧${NC} $*"; }
section(){ echo -e "\n${BOLD}── $* ──${NC}"; }

ALTROOT="/" FIX=0 DRY=0 JSON_OUT=0 FILTER=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --altroot)  ALTROOT="${2%/}"; shift 2 ;;
        --fix)      FIX=1; shift ;;
        --dry-run)  DRY=1; shift ;;
        --json)     JSON_OUT=1; shift ;;
        --preset)   FILTER="$2"; shift 2 ;;
        --boot)     BOOT="$2"; shift 2 ;;
        -h|--help)  grep '^#' "$0" | head -30 | sed 's/^# \?//'; exit 0 ;;
        *) echo "Argument inconnu : $1"; exit 1 ;;
    esac
done

# Sur Debian live /boot est occupé — utiliser zbm_locate_boot() pour BOOT
if [[ -z "${BOOT:-}" ]]; then
    zbm_locate_boot 2>/dev/null || true
fi
[[ "$ALTROOT" != "/" ]] && [[ -n "$ALTROOT" ]] && BOOT="${ALTROOT}/boot"
# Fallback si zbm_locate_boot n'a pas trouvé
BOOT="${BOOT:-${ZBM_BOOT:-/mnt/zbm/boot}}"
PRESETS_DIR="$BOOT/presets"
ERRORS=0; WARNINGS=0; FIXES=0
JSON_ITEMS=()

zfs_get() { zfs get -H -o value "$2" "$1" 2>/dev/null || echo ""; }
ds_exists() { zfs list "$1" >/dev/null 2>&1; }

canon_mp() {
    local ds="$1"
    case "$ds" in
        fast_pool/overlay-*)  echo "none" ;;
        # var-*/log-*/tmp-* supprimés : architecture overlay (lower=rootfs.sfs)
        data_pool/home)      echo "/home" ;;
        data_pool/archives*) echo "none" ;;
        boot_pool)           echo "legacy" ;;
        *)                   echo "" ;;
    esac
}

eff_mp() {
    local mp="$1"
    [[ "$mp" == "none" ]] || [[ "$mp" == "legacy" ]] || [[ -z "$mp" ]] && echo "$mp" && return
    [[ "$ALTROOT" == "/" ]] && echo "$mp" || echo "${ALTROOT}${mp}"
}

read_preset_field() { python3 -c "
import json,sys
try: d=json.load(open('$1')); v=d.get('$2'); print('' if v is None else v)
except: pass" 2>/dev/null; }

do_fix() {
    local cmd="$1" desc="$2"
    if [[ $DRY -eq 1 ]]; then
        fix_ln "[dry-run] $desc"
    elif [[ $FIX -eq 1 ]]; then
        if eval "$cmd"; then fix_ln "$desc"; FIXES=$((FIXES+1))
        else err_ln "Correction échouée : $desc"; fi
    fi
}

# =============================================================================
# A. NOMMAGE
# =============================================================================
check_names() {
    section "A. Nommage des images"
    local bad=0

    for dir in \
        "$BOOT/images/kernels" "$BOOT/images/initramfs" \
        "$BOOT/images/modules" "$BOOT/images/rootfs"    \
        "$BOOT/images/startup" "$BOOT/images/failsafe"; do
        [[ -d "$dir" ]] || continue
        for f in "$dir"/*; do
            [[ -f "$f" ]] && [[ "$f" != *.meta ]] || continue
            if ! zbm_validate_name "$f"; then
                err_ln "Non conforme : $(basename "$f")  (dans $dir)"
                ERRORS=$((ERRORS+1)); bad=$((bad+1))
                JSON_ITEMS+=("{\"check\":\"name\",\"status\":\"nonconform\",\"file\":\"$f\"}")
            elif [[ ! -f "$(zbm_meta "$f")" ]]; then
                warn "Meta absent : $(basename "$f").meta"
                WARNINGS=$((WARNINGS+1))
                do_fix "zbm_write_meta '$f'" "Meta créé : $(basename "$f").meta"
            fi
        done
    done

    # Kernels/initramfs/modules : vérifier qu'il n'y a pas de rootfs dans kernels/
    for f in "$BOOT/images/kernels"/*; do
        [[ -f "$f" ]] && [[ "$f" != *.meta ]] || continue
        local p; p=$(zbm_parse "$f") || continue; eval "$p"
        if [[ "$ZBM_TYPE" != "kernel" ]]; then
            warn "Fichier de type '$ZBM_TYPE' dans kernels/ : $(basename "$f")"
            WARNINGS=$((WARNINGS+1))
        fi
    done

    # Python SFS
    local py_count; py_count=$(ls "$BOOT/images/startup/"python-*.sfs 2>/dev/null | grep -v '\.meta$' | wc -l || echo 0)
    if [[ $py_count -eq 0 ]]; then
        warn "Aucun python-*.sfs — lancez python-sfs.sh (non bloquant)"
        WARNINGS=$((WARNINGS+1))
    else
        ok "Python SFS : $py_count fichier(s)"
    fi

    # Lister les ensembles kernel+initramfs
    echo ""
    echo -e "  ${DIM}Ensembles kernel/initramfs :${NC}"
    local found_sets=0
    zbm_list_sets --all | while IFS=' ' read -r klbl ilbl dt has_mod; do
        found_sets=$((found_sets+1))
        local mod_info=""; [[ $has_mod -eq 1 ]] && mod_info=" +modules"
        local complete_sym="✅"
        [[ "$ilbl" == "none" ]] && complete_sym="⚠️ (pas d'initramfs)"
        echo "  ${complete_sym}  kernel=${klbl}  init=${ilbl}  date=${dt}${mod_info}"
    done || true

    # Lister les rootfs (indépendants)
    echo ""
    echo -e "  ${DIM}Rootfs disponibles (indépendants) :${NC}"
    local found_rootfs=0
    zbm_list_rootfs | while IFS=' ' read -r rsys rlbl rdt; do
        found_rootfs=$((found_rootfs+1))
        echo "    rootfs-${rsys}-${rlbl}-${rdt}.sfs"
    done || true

    [[ $bad -eq 0 ]] && ok "Convention de nommage respectée"
}

# =============================================================================
# B. PRESETS
# =============================================================================
check_preset_files() {
    local pfile="$1" name="$2"

    local init_type; init_type=$(read_preset_field "$pfile" init_type)
    local ptype;     ptype=$(read_preset_field "$pfile" type)

    # Kernel (toujours requis sauf failsafe)
    local kernel; kernel=$(read_preset_field "$pfile" kernel)
    if [[ -n "$kernel" ]]; then
        if [[ ! -f "$kernel" ]]; then
            err_ln "[$name] kernel : introuvable → $kernel"
            ERRORS=$((ERRORS+1))
        else
            zbm_validate_name "$kernel" \
                || warn "[$name] kernel : nom hors convention → $(basename "$kernel")"
        fi
    fi

    # Initramfs (toujours requis)
    local initrd; initrd=$(read_preset_field "$pfile" initramfs)
    if [[ -n "$initrd" ]]; then
        if [[ ! -f "$initrd" ]]; then
            err_ln "[$name] initramfs : introuvable → $initrd"
            ERRORS=$((ERRORS+1))
        else
            zbm_validate_name "$initrd" \
                || warn "[$name] initramfs : nom hors convention → $(basename "$initrd")"
            # Vérifier cohérence type init
            local meta_it; meta_it=$(zbm_read_meta "$initrd" "init_type" 2>/dev/null || true)
            if [[ -n "$init_type" ]] && [[ -n "$meta_it" ]] && [[ "$init_type" != "$meta_it" ]]; then
                warn "[$name] init_type=$init_type ≠ meta init_type=$meta_it"
                WARNINGS=$((WARNINGS+1))
            fi
        fi
    fi

    # Modules (optionnels)
    local modules; modules=$(read_preset_field "$pfile" modules)
    if [[ -n "$modules" ]] && [[ "$modules" != "null" ]]; then
        if [[ ! -f "$modules" ]]; then
            err_ln "[$name] modules : introuvable → $modules"
            ERRORS=$((ERRORS+1))
        else
            zbm_validate_name "$modules" \
                || warn "[$name] modules : nom hors convention"
        fi
    fi

    # Rootfs (optionnel — null valide pour preset initial)
    local rootfs; rootfs=$(read_preset_field "$pfile" rootfs)
    if [[ -n "$rootfs" ]] && [[ "$rootfs" != "null" ]]; then
        if [[ ! -f "$rootfs" ]]; then
            err_ln "[$name] rootfs : introuvable → $rootfs"
            ERRORS=$((ERRORS+1))
        else
            zbm_validate_name "$rootfs" \
                || warn "[$name] rootfs : nom hors convention"
        fi
    elif [[ "$name" != "initial" ]] && [[ "$name" != "failsafe" ]] && \
         [[ "$ptype" != "minimal" ]]; then
        warn "[$name] rootfs=null — preset sans système de fichiers cible"
        WARNINGS=$((WARNINGS+1))
    fi

    # Cmdline
    local cmdline; cmdline=$(read_preset_field "$pfile" cmdline)
    if [[ -n "$cmdline" ]]; then
        # Vérifier zbm_rootfs dans cmdline si rootfs défini
        if [[ -n "$rootfs" ]] && [[ "$rootfs" != "null" ]]; then
            local cmd_rootfs; cmd_rootfs=$(echo "$cmdline" | grep -oP 'zbm_rootfs=\K\S+' || true)
            if [[ -n "$cmd_rootfs" ]] && [[ "$cmd_rootfs" != "$rootfs" ]]; then
                err_ln "[$name] cmdline zbm_rootfs≠rootfs : $cmd_rootfs ≠ $rootfs"
                ERRORS=$((ERRORS+1))
                do_fix "python3 -c \"
import json, re
d=json.load(open('$pfile'))
d['cmdline']=re.sub(r'zbm_rootfs=\\S+',f'zbm_rootfs=${rootfs}',d['cmdline'])
json.dump(d,open('$pfile','w'),indent=2)
\"" "Cmdline zbm_rootfs corrigée [$name]"
            fi
        fi
        # Vérifier zbm_modules dans cmdline
        if [[ -n "$modules" ]] && [[ "$modules" != "null" ]]; then
            local cmd_mod; cmd_mod=$(echo "$cmdline" | grep -oP 'zbm_modules=\K\S+' || true)
            if [[ -n "$cmd_mod" ]] && [[ "$cmd_mod" != "$modules" ]]; then
                err_ln "[$name] cmdline zbm_modules≠modules : $cmd_mod ≠ $modules"
                ERRORS=$((ERRORS+1))
            fi
        fi
    fi
}

check_presets() {
    section "B. Presets de boot"
    [[ -d "$PRESETS_DIR" ]] || { warn "Répertoire presets absent : $PRESETS_DIR"; return; }

    for pfile in "$PRESETS_DIR"/*.json; do
        [[ -f "$pfile" ]] || continue
        local name; name=$(read_preset_field "$pfile" name)
        [[ -z "$name" ]] && continue
        [[ -n "$FILTER" ]] && [[ "$name" != "$FILTER" ]] && continue

        local ptype; ptype=$(read_preset_field "$pfile" type)
        local init_type; init_type=$(read_preset_field "$pfile" init_type)
        local prot; prot=$(read_preset_field "$pfile" protected)
        echo ""
        echo -e "  ${BOLD}[${name}]${NC}  type=${ptype}  init=${init_type}${prot:+  🔒}"

        [[ "$prot" == "True" ]] || [[ "$prot" == "true" ]] && { ok "[$name] Protected — ignoré"; continue; }
        check_preset_files "$pfile" "$name"
        ok "[$name] Vérifié"
    done

    # Conflits de datasets entre presets
    echo ""
    declare -A DS_OWNERS
    local conflicts=0
    for pfile in "$PRESETS_DIR"/*.json; do
        [[ -f "$pfile" ]] || continue
        local name; name=$(read_preset_field "$pfile" name)
        for field in var_dataset log_dataset tmp_dataset; do
            local ds; ds=$(read_preset_field "$pfile" "$field")
            [[ -z "$ds" ]] || [[ "$ds" == "null" ]] && continue
            if [[ -n "${DS_OWNERS[$ds]+x}" ]] && [[ "${DS_OWNERS[$ds]}" != "$name" ]]; then
                err_ln "CONFLIT : $ds utilisé par '${name}' ET '${DS_OWNERS[$ds]}'"
                ERRORS=$((ERRORS+1)); conflicts=$((conflicts+1))
            else
                DS_OWNERS[$ds]="$name"
            fi
        done
    done
    [[ $conflicts -eq 0 ]] && ok "Aucun conflit de datasets entre presets"
}

# =============================================================================
# C. DATASETS ZFS
# =============================================================================
check_zfs() {
    section "C. Datasets ZFS"

    # boot_pool
    if ! zpool list boot_pool >/dev/null 2>&1; then
        err_ln "boot_pool non importé"
        ERRORS=$((ERRORS+1)); return
    fi
    local bmp; bmp=$(zfs_get boot_pool mountpoint)
    # boot_pool doit avoir mountpoint=legacy (ZBM gère le montage)
    if [[ "$bmp" == "legacy" ]]; then
        ok "boot_pool  mp=legacy"
    elif [[ "$bmp" == "/boot" ]]; then
        warn "boot_pool  mp=/boot (ancien — devrait être legacy)"
        ERRORS=$((ERRORS+1))
        do_fix "zfs set mountpoint=legacy boot_pool" "boot_pool mountpoint=legacy"
    else
        err_ln "boot_pool  mp=$bmp (attendu: legacy)"
        ERRORS=$((ERRORS+1))
        do_fix "zfs set mountpoint=legacy boot_pool" "boot_pool mountpoint=legacy"
    fi

    # Datasets des presets
    for pfile in "$PRESETS_DIR"/*.json; do
        [[ -f "$pfile" ]] || continue
        local name; name=$(read_preset_field "$pfile" name)
        [[ -z "$name" ]] && continue
        [[ -n "$FILTER" ]] && [[ "$name" != "$FILTER" ]] && continue
        [[ $(read_preset_field "$pfile" protected) == "true" ]] && continue

        for field in overlay_dataset var_dataset log_dataset tmp_dataset home_dataset; do
            local ds; ds=$(read_preset_field "$pfile" "$field")
            [[ -z "$ds" ]] || [[ "$ds" == "null" ]] && continue
            local exp; exp=$(canon_mp "$ds")
            [[ -z "$exp" ]] && continue

            if ! ds_exists "$ds"; then
                err_ln "[$name] $field : dataset absent → $ds"
                ERRORS=$((ERRORS+1))
                JSON_ITEMS+=("{\"check\":\"zfs\",\"preset\":\"$name\",\"ds\":\"$ds\",\"status\":\"missing\"}")
                continue
            fi
            local actual; actual=$(zfs_get "$ds" mountpoint)
            local eff; eff=$(eff_mp "$exp")
            if [[ "$actual" == "$exp" ]] || [[ "$actual" == "$eff" ]]; then
                ok "[$name] $ds  mp=$actual"
            else
                err_ln "[$name] $ds  mp=$actual (attendu: $exp)"
                ERRORS=$((ERRORS+1))
                # fast_pool/* : ne pas forcer le montage — juste corriger la prop ZFS
                # Le montage réel est fait par initramfs-init, pas ici
                do_fix "zfs set mountpoint=${exp} ${ds}" "$ds mountpoint→$exp"
            fi
            # Vérifier canmount=noauto sur fast_pool/*
            if [[ "$ds" == fast_pool/* ]]; then
                local cm; cm=$(zfs_get "$ds" canmount)
                if [[ "$cm" != "noauto" ]]; then
                    warn "$ds canmount=$cm (devrait être noauto)"
                    WARNINGS=$((WARNINGS+1))
                    do_fix "zfs set canmount=noauto $ds" "$ds canmount→noauto"
                fi
            fi
            # Recommandations
            local comp; comp=$(zfs_get "$ds" compression)
            [[ "$comp" == "off" ]] && { warn "$ds compression=off"; WARNINGS=$((WARNINGS+1))
                do_fix "zfs set compression=zstd $ds" "$ds compression→zstd"; }
            local atime; atime=$(zfs_get "$ds" atime)
            [[ "$atime" == "on" ]] && { warn "$ds atime=on"; WARNINGS=$((WARNINGS+1))
                do_fix "zfs set atime=off $ds" "$ds atime→off"; }
        done
    done

    # Symlinks /boot
    echo ""
    echo -e "  ${DIM}Symlinks /boot/boot/ (actifs pour ZBM) :${NC}"
    # Les symlinks actifs sont dans $BOOT/boot/ = ZBM_BOOT_LINKS (créés par presets.sh)
    # ZBM monte boot_pool comme BE et cherche <be_root>/boot/vmlinuz
    local BOOT_LINK_DIR="$BOOT/boot"
    for link in "vmlinuz" "initrd.img" "modules.sfs" "rootfs.sfs"; do
        local lp="$BOOT_LINK_DIR/$link"
        if [[ ! -L "$lp" ]]; then
            warn "Symlink absent : $link  (normal si preset initial/stream)"
            WARNINGS=$((WARNINGS+1))
        elif [[ ! -e "$lp" ]]; then
            local tgt; tgt=$(readlink "$lp")
            err_ln "Symlink cassé : $link → $tgt"
            ERRORS=$((ERRORS+1))
        else
            local tgt; tgt=$(readlink "$lp")
            zbm_validate_name "$tgt" \
                && ok "$link → $(basename "$tgt")" \
                || warn "$link → $(basename "$tgt")  (cible hors convention)"
        fi
    done
}

# =============================================================================
# MAIN
# =============================================================================
if [[ $JSON_OUT -eq 0 ]]; then
    echo -e "\n${CYAN}${BOLD}"
    echo "╔══════════════════════════════════════════════════════════╗"
    echo "║   ZBM — Cohérence système                                ║"
    echo "╚══════════════════════════════════════════════════════════╝${NC}"
    echo "  Boot : $BOOT | Altroot : $ALTROOT"
    [[ $FIX -eq 1 ]] && echo -e "  Mode : ${GREEN}--fix${NC}"
    [[ $DRY -eq 1 ]] && echo -e "  Mode : ${YELLOW}--dry-run${NC}"
fi

check_names
check_presets
check_zfs

if [[ $JSON_OUT -eq 1 ]]; then
    printf '{"errors":%d,"warnings":%d,"fixes":%d,"items":[' "$ERRORS" "$WARNINGS" "$FIXES"
    first=1
    for item in "${JSON_ITEMS[@]:-}"; do
        [[ $first -eq 0 ]] && printf ","
        printf '%s' "$item"; first=0
    done
    printf ']}\n'
else
    section "Résumé"
    printf "  Erreurs   : %d\n" "$ERRORS"
    printf "  Warnings  : %d\n" "$WARNINGS"
    [[ $FIX -eq 1 ]] && printf "  Corrections : %d\n" "$FIXES"
    echo ""
    if [[ $ERRORS -eq 0 ]] && [[ $WARNINGS -eq 0 ]]; then
        echo -e "  ${GREEN}${BOLD}✅ Cohérence parfaite${NC}"
    elif [[ $ERRORS -eq 0 ]]; then
        echo -e "  ${YELLOW}⚠️  $WARNINGS avertissement(s) — système fonctionnel${NC}"
    else
        echo -e "  ${RED}❌ $ERRORS erreur(s) à corriger${NC}"
        [[ $FIX -eq 0 ]] && [[ $DRY -eq 0 ]] && echo \
            "  → bash lib/coherence.sh --fix  [ou --dry-run pour prévisualiser]"
    fi
fi

exit $([[ $ERRORS -eq 0 ]] && echo 0 || echo 1)
