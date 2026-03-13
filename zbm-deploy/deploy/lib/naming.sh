#!/bin/bash
# =============================================================================
# lib/naming.sh — Convention de nommage unifiée pour toutes les images /boot
#
# ─── PRINCIPE FONDAMENTAL ────────────────────────────────────────────────────
#
#   Kernels, initramfs et modules sont INDÉPENDANTS des systèmes rootfs.
#   Un preset de boot combine librement :
#     kernel  + initramfs + modules (optionnel) + rootfs (optionnel)
#   Le rootfs NE CONTIENT NI kernel NI modules — ce sont des objets séparés.
#
# ─── CONVENTION ──────────────────────────────────────────────────────────────
#
#   TYPE        NOM DE FICHIER                       EXT    RÉPERTOIRE
#   kernel      kernel-<label>-<YYYYMMDD>            ""     images/kernels/
#   initramfs   initramfs-<label>-<YYYYMMDD>         .img   images/initramfs/
#   modules     modules-<label>-<YYYYMMDD>           .sfs   images/modules/
#   rootfs      rootfs-<system>-<label>-<YYYYMMDD>   .sfs   images/rootfs/
#   python      python-<ver>-<YYYYMMDD>              .sfs   images/startup/
#   (failsafe)  *-failsafe-<label>-<YYYYMMDD>[ext]          images/failsafe/
#
#   kernel/initramfs/modules : PAS de champ "system" — indépendants
#   rootfs SEULEMENT a un champ "system"
#
# ─── TYPES D'INIT (label de l'initramfs) ────────────────────────────────────
#
#   zbm            Notre init squashfs+overlayfs+python TUI (+ stream optionnel)
#   zbm-stream     Variante : sans TUI Python, flux video direct
#   minimal        Init natif fourni avec le noyau, boot direct rootfs
#   custom-<nom>   Init personnalisé
#
# ─── EXEMPLES ────────────────────────────────────────────────────────────────
#
#   kernel-generic-6.12-20250305
#   kernel-custom-i5-11400-6.12-20250305
#   initramfs-zbm-20250305.img
#   initramfs-zbm-stream-20250305.img
#   initramfs-minimal-20250305.img
#   modules-generic-6.12-20250305.sfs
#   rootfs-systeme1-gentoo-20250305.sfs
#   python-3.11-20250305.sfs
#   kernel-failsafe-generic-6.12-20250305
#   rootfs-failsafe-gentoo-20250305.sfs
#
# ─── API ─────────────────────────────────────────────────────────────────────
#
#   zbm_ext <type>
#   zbm_dir <type>
#   zbm_stem <type> <system_or_empty> <label> [<date>]
#   zbm_path <type> <system_or_empty> <label> [<date>]
#   zbm_meta <image_path>
#   zbm_latest <type> <system_or_empty> <label>
#   zbm_parse <filename>           → ZBM_TYPE SYSTEM LABEL DATE EXT (eval)
#   zbm_validate_name <path>
#   zbm_list_sets [--all]          → ensembles kernel+initramfs
#   zbm_list_rootfs                → rootfs disponibles
#   zbm_set_complete <klabel> <date>
#   zbm_active_links <klbl> <ilbl> <date> [<mlbl>] [<rsys> <rlbl>]
#   zbm_failsafe_links <label> <date>
#   zbm_write_meta <image_path> [clé=val ...]
#   zbm_read_meta <image_path> <clé>
#   zbm_check_orphans
#   zbm_init_type <initramfs_path>
#
# =============================================================================

# =============================================================================
# zbm_locate_boot  — Localisation UNIFIÉE de boot_pool
#
# Sur Debian live, /boot appartient au live CD.
# boot_pool a mountpoint=legacy → jamais monté automatiquement.
# Ce script monte TOUJOURS boot_pool sur /mnt/zbm/boot (pas /boot, occupé par le live).
#
# Résultat : exporte $BOOT = chemin réel de boot_pool.
#
# Règles :
#   1. $BOOT déjà défini et monté → réutiliser
#   2. zfs mount → trouver le mountpoint actuel
#   3. monter sur $ZBM_BOOT=/mnt/zbm/boot  (JAMAIS /boot sur le live)
#
# Usage :
#   zbm_locate_boot   # exporte BOOT, définit _MOUNTED_BOOT_LIVE
#   Cleanup manuel via zbm_cleanup_boot
# =============================================================================

# Charger les constantes de montage (source de vérité)
_MOUNTS_SH="$(dirname "${BASH_SOURCE[0]}")/mounts.sh"
[[ -f "$_MOUNTS_SH" ]] && source "$_MOUNTS_SH"

# Chemin canonique boot_pool sur le live (depuis mounts.sh)
ZBM_LIVE_ROOT="${ZBM_BOOT:-/mnt/zbm/boot}"
_MOUNTED_BOOT_LIVE=0

zbm_locate_boot() {
    # Priorité 1 : BOOT déjà défini et monté
    if [[ -n "${BOOT:-}" ]] && mountpoint -q "${BOOT}" 2>/dev/null; then
        # S'assurer que boot_pool/images est aussi monté
        zbm_ensure_images_dataset 2>/dev/null || true
        export BOOT
        return 0
    fi

    # Priorité 2 : zfs mount → chercher boot_pool déjà monté
    local _cur
    _cur=$(zfs mount 2>/dev/null | awk '$1=="boot_pool"{print $2}' | head -1 || true)
    if [[ -n "$_cur" ]]; then
        BOOT="$_cur"
        zbm_ensure_images_dataset 2>/dev/null || true
        export BOOT
        return 0
    fi

    # boot_pool pas monté → import si nécessaire
    if ! zpool list boot_pool >/dev/null 2>&1; then
        zpool import -N boot_pool 2>/dev/null || true
    fi

    # Priorité 3 : monter sur ZBM_LIVE_ROOT (jamais /boot = occupé sur live)
    BOOT="$ZBM_LIVE_ROOT"
    mkdir -p "$BOOT"
    if mount -t zfs boot_pool "$BOOT" 2>/dev/null; then
        _MOUNTED_BOOT_LIVE=1
        zbm_ensure_images_dataset 2>/dev/null || true
        export BOOT _MOUNTED_BOOT_LIVE
        return 0
    fi
    # ZBM_LIVE_ROOT occupé (déjà monté par autre processus ?) → attendre ou échouer
    # Ne jamais créer un répertoire temporaire aléatoire : casse umount.sh et la cohérence
    echo "zbm_locate_boot: $ZBM_LIVE_ROOT occupé et boot_pool non montable" >&2
    BOOT=""
    return 1
}

zbm_cleanup_boot() {
    [[ "${_MOUNTED_BOOT_LIVE:-0}" -eq 1 ]] || return 0
    # Démonter boot_pool/images AVANT boot_pool (enfant ZFS normal → zfs unmount)
    zfs unmount boot_pool/images 2>/dev/null || true
    umount "${BOOT:-}" 2>/dev/null || true
    # Supprimer seulement si c'est un répertoire temporaire que nous avons créé
    case "${BOOT:-}" in
        "${ZBM_BOOT:-/mnt/zbm/boot}")
            # Répertoire créé par nous — ne retirer que le sous-répertoire images
            # (le répertoire boot lui-même peut être voulu par le système)
            : ;;
    esac
    _MOUNTED_BOOT_LIVE=0
}


_zbm_sanitize() { echo "$1" | tr ' /_' '---' | tr -cd 'a-zA-Z0-9.\-'; }

zbm_ext() {
    case "$1" in
        kernel)    echo "" ;;
        initramfs) echo ".img" ;;
        modules)   echo ".sfs" ;;
        rootfs)    echo ".sfs" ;;
        python)    echo ".sfs" ;;
        *)         echo "" ;;
    esac
}

zbm_dir() {
    local type="$1" BOOT="${BOOT:-/boot}"
    case "$type" in
        kernel)    echo "$BOOT/images/kernels" ;;
        initramfs) echo "$BOOT/images/initramfs" ;;
        modules)   echo "$BOOT/images/modules" ;;
        rootfs)    echo "$BOOT/images/rootfs" ;;
        python)    echo "$BOOT/images/startup" ;;
        failsafe)  echo "$BOOT/images/failsafe" ;;
        *)         echo "$BOOT/images" ;;
    esac
}

# zbm_ensure_images_dataset  — Crée et monte boot_pool/images si absent.
#
# boot_pool/images est un dataset ZFS enfant de boot_pool, comme boot_pool lui-même
# il a mountpoint=legacy → monté explicitement sur $BOOT/images.
# Les sous-dossiers (kernels/, initramfs/, rootfs/, modules/, startup/, failsafe/)
# sont de simples répertoires dans ce dataset.
#
# Prérequis : $BOOT doit être défini et boot_pool monté sur $BOOT.
# Retourne 1 si BOOT non défini, non monté, ou si la création ZFS échoue.
zbm_ensure_images_dataset() {
    local _boot="${BOOT:-}"

    if [[ -z "$_boot" ]] || ! mountpoint -q "$_boot" 2>/dev/null; then
        echo "zbm_ensure_images_dataset: boot_pool non monté (${_boot:-<vide>})" >&2
        return 1
    fi

    local _images_mp="${_boot}/images"

    # Si déjà monté → juste créer les sous-dossiers manquants
    if mountpoint -q "$_images_mp" 2>/dev/null; then
        :
    # Sinon, vérifier que le dataset existe et le monter via "zfs mount"
    elif zfs list boot_pool/images >/dev/null 2>&1; then
        mkdir -p "$_images_mp"
        if ! zfs mount boot_pool/images 2>/dev/null; then
            echo "zbm_ensure_images_dataset: zfs mount boot_pool/images échoué" >&2
            return 1
        fi
        echo "  → boot_pool/images monté sur $_images_mp" >&2
    else
        # Dataset absent — sera créé par datasets-check.sh
        echo "zbm_ensure_images_dataset: boot_pool/images absent — lancez datasets-check.sh --initial" >&2
        return 1
    fi

    # Créer les sous-dossiers standards si manquants (simples répertoires dans le dataset)
    local _d _created=0
    for _d in kernels initramfs modules rootfs startup failsafe; do
        if [[ ! -d "$_images_mp/$_d" ]]; then
            mkdir -p "$_images_mp/$_d" && _created=$((_created + 1))
        fi
    done
    [[ $_created -gt 0 ]] && \
        echo "  → $_created sous-dossier(s) créé(s) dans $_images_mp" >&2 || true

    return 0
}

# zbm_stem <type> <system_or_empty> <label> [<date>]
zbm_stem() {
    local type="$1" system="$2" label
    label=$(_zbm_sanitize "$3")
    local date="${4:-$(date +%Y%m%d)}"
    local ext; ext=$(zbm_ext "$type")
    case "$type" in
        python)
            echo "python-${label}-${date}${ext}" ;;
        rootfs)
            echo "rootfs-${system}-${label}-${date}${ext}" ;;
        kernel|initramfs|modules)
            if [[ "$system" == "failsafe" ]]; then
                echo "${type}-failsafe-${label}-${date}${ext}"
            else
                echo "${type}-${label}-${date}${ext}"
            fi ;;
        *)
            echo "${type}-${label}-${date}${ext}" ;;
    esac
}

zbm_path() {
    local type="$1" system="$2" label="$3" date="${4:-$(date +%Y%m%d)}"
    local dir
    [[ "$system" == "failsafe" ]] && dir="$(zbm_dir failsafe)" || dir="$(zbm_dir "$type")"
    echo "$dir/$(zbm_stem "$type" "$system" "$label" "$date")"
}

zbm_meta() { echo "${1}.meta"; }

zbm_latest() {
    local type="$1" system="$2" label
    label=$(_zbm_sanitize "$3")
    local dir ext
    [[ "$system" == "failsafe" ]] && dir="$(zbm_dir failsafe)" || dir="$(zbm_dir "$type")"
    ext=$(zbm_ext "$type")
    local pattern
    case "$type" in
        python)    pattern="${dir}/python-${label}-"????????"${ext}" ;;
        rootfs)    pattern="${dir}/rootfs-${system}-${label}-"????????"${ext}" ;;
        kernel|initramfs|modules)
            if [[ "$system" == "failsafe" ]]; then
                pattern="${dir}/${type}-failsafe-${label}-"????????"${ext}"
            else
                pattern="${dir}/${type}-${label}-"????????"${ext}"
            fi ;;
        *)         pattern="${dir}/${type}-${label}-"????????"${ext}" ;;
    esac
    ls $pattern 2>/dev/null | sort | tail -1 || true
}

# zbm_parse <path>
# Retourne une chaîne eval-able ou exit 1 si non conforme.
zbm_parse() {
    local fname; fname=$(basename "$1")
    local stem="$fname" ZBM_EXT=""
    [[ "$fname" == *.meta ]] && return 1
    case "$stem" in
        *.img) ZBM_EXT=".img"; stem="${stem%.img}" ;;
        *.sfs) ZBM_EXT=".sfs"; stem="${stem%.sfs}" ;;
    esac
    local ZBM_TYPE=""
    for t in kernel initramfs modules rootfs python; do
        if [[ "$stem" == "${t}-"* ]]; then
            ZBM_TYPE="$t"; stem="${stem#${t}-}"; break
        fi
    done
    [[ -z "$ZBM_TYPE" ]] && return 1
    local tail="${stem: -8}"
    [[ "$tail" =~ ^[0-9]{8}$ ]] || return 1
    local ZBM_DATE="$tail"
    stem="${stem:0:${#stem}-9}"
    local ZBM_SYSTEM="" ZBM_LABEL=""
    case "$ZBM_TYPE" in
        python)
            ZBM_SYSTEM=""; ZBM_LABEL="$stem" ;;
        rootfs)
            ZBM_SYSTEM="${stem%%-*}"; ZBM_LABEL="${stem#*-}"
            [[ -z "$ZBM_SYSTEM" ]] && return 1 ;;
        kernel|initramfs|modules)
            if [[ "$stem" == "failsafe-"* ]]; then
                ZBM_SYSTEM="failsafe"; ZBM_LABEL="${stem#failsafe-}"
            else
                ZBM_SYSTEM=""; ZBM_LABEL="$stem"
            fi ;;
        *)  ZBM_SYSTEM=""; ZBM_LABEL="$stem" ;;
    esac
    [[ -z "$ZBM_LABEL" ]] && return 1
    echo "ZBM_TYPE=${ZBM_TYPE} ZBM_SYSTEM=${ZBM_SYSTEM} ZBM_LABEL=${ZBM_LABEL} ZBM_DATE=${ZBM_DATE} ZBM_EXT=${ZBM_EXT}"
}

zbm_validate_name() { zbm_parse "$1" >/dev/null 2>&1; }

# zbm_list_sets [--all]
# Sortie : "<kernel_label> <initramfs_label|none> <date> <has_modules:0|1>"
zbm_list_sets() {
    local ALL=0; [[ "${1:-}" == "--all" ]] && ALL=1
    local BOOT="${BOOT:-/boot}"
    declare -A KERNELS INITRAMFS_DATES MODULES
    local dir_k; dir_k=$(zbm_dir kernel)
    local dir_i; dir_i=$(zbm_dir initramfs)
    local dir_m; dir_m=$(zbm_dir modules)
    for f in "$dir_k"/kernel-*; do
        [[ -f "$f" ]] && [[ "$f" != *.meta ]] || continue
        local p; p=$(zbm_parse "$f") || continue; eval "$p"
        [[ "$ZBM_SYSTEM" == "failsafe" ]] && continue
        KERNELS["${ZBM_LABEL}:${ZBM_DATE}"]=1
    done
    for f in "$dir_i"/initramfs-*; do
        [[ -f "$f" ]] && [[ "$f" != *.meta ]] || continue
        local p; p=$(zbm_parse "$f") || continue; eval "$p"
        [[ "$ZBM_SYSTEM" == "failsafe" ]] && continue
        INITRAMFS_DATES["${ZBM_DATE}:${ZBM_LABEL}"]=1
    done
    for f in "$dir_m"/modules-*; do
        [[ -f "$f" ]] && [[ "$f" != *.meta ]] || continue
        local p; p=$(zbm_parse "$f") || continue; eval "$p"
        [[ "$ZBM_SYSTEM" == "failsafe" ]] && continue
        MODULES["${ZBM_LABEL}:${ZBM_DATE}"]=1
    done
    for kkey in "${!KERNELS[@]}"; do
        local klabel="${kkey%%:*}" kdate="${kkey##*:}"
        local found_init="none" has_mod=0
        for ikey in "${!INITRAMFS_DATES[@]}"; do
            local idate="${ikey%%:*}" ilabel="${ikey##*:}"
            if [[ "$idate" == "$kdate" ]]; then found_init="$ilabel"; break; fi
        done
        for mkey in "${!MODULES[@]}"; do
            local mlabel="${mkey%%:*}" mdate="${mkey##*:}"
            if [[ "$mdate" == "$kdate" ]]; then has_mod=1; break; fi
        done
        if [[ "$found_init" != "none" ]] || [[ $ALL -eq 1 ]]; then
            echo "${klabel} ${found_init} ${kdate} ${has_mod}"
        fi
    done | sort
}

# zbm_list_rootfs
zbm_list_rootfs() {
    local dir; dir=$(zbm_dir rootfs)
    [[ -d "$dir" ]] || return 0
    for f in "$dir"/rootfs-*; do
        [[ -f "$f" ]] && [[ "$f" != *.meta ]] || continue
        local p; p=$(zbm_parse "$f") || continue; eval "$p"
        [[ "$ZBM_SYSTEM" == "failsafe" ]] && continue
        echo "$ZBM_SYSTEM $ZBM_LABEL $ZBM_DATE"
    done | sort
}

# zbm_set_complete <kernel_label> <date>
zbm_set_complete() {
    local klabel="$1" date="$2"
    [[ -f "$(zbm_path kernel "" "$klabel" "$date")" ]] || return 1
    local dir_i; dir_i=$(zbm_dir initramfs)
    for f in "$dir_i"/initramfs-*"-${date}.img"; do
        [[ -f "$f" ]] && return 0
    done
    return 1
}

# zbm_active_links <klbl> <ilbl> <date> [<mlbl>] [<rsys> <rlbl>]
# Utilisé comme référence par presets.sh (_mk_link) et python-interface.py
zbm_active_links() {
    local klbl="$1" ilbl="$2" dt="$3" mlbl="${4:-}" rsys="${5:-}" rlbl="${6:-}"
    echo "vmlinuz|images/kernels/$(zbm_stem kernel "" "$klbl" "$dt")"
    echo "initrd.img|images/initramfs/$(zbm_stem initramfs "" "$ilbl" "$dt")"
    [[ -n "$mlbl" ]] && echo "modules.sfs|images/modules/$(zbm_stem modules "" "$mlbl" "$dt")"
    [[ -n "$rsys" ]] && [[ -n "$rlbl" ]] && \
        echo "rootfs.sfs|images/rootfs/$(zbm_stem rootfs "$rsys" "$rlbl" "$dt")"
}

zbm_failsafe_links() {
    local lbl="$1" dt="$2"
    echo "vmlinuz.failsafe|images/failsafe/$(zbm_stem kernel failsafe "$lbl" "$dt")"
    echo "initrd.failsafe.img|images/failsafe/$(zbm_stem initramfs failsafe "$lbl" "$dt")"
    echo "modules.failsafe.sfs|images/failsafe/$(zbm_stem modules failsafe "$lbl" "$dt")"
    echo "rootfs.failsafe.sfs|images/failsafe/$(zbm_stem rootfs failsafe "$lbl" "$dt")"
}

zbm_write_meta() {
    local img="$1"; shift
    local meta; meta=$(zbm_meta "$img")
    local p; p=$(zbm_parse "$img") || { echo "zbm_write_meta: nom non conforme: $img" >&2; return 1; }
    eval "$p"
    local size_bytes=0 sha256="" built kernel_ver="" init_type="" builder="zbm-deploy"
    built=$(date -Iseconds)
    [[ -f "$img" ]] && size_bytes=$(stat -c%s "$img" 2>/dev/null || echo 0)
    [[ -f "$img" ]] && sha256=$(sha256sum "$img" 2>/dev/null | awk '{print $1}' || echo "")
    for kv in "$@"; do
        case "$kv" in
            kernel_ver=*) kernel_ver="${kv#*=}" ;;
            init_type=*)  init_type="${kv#*=}" ;;
            builder=*)    builder="${kv#*=}" ;;
            built=*)      built="${kv#*=}" ;;
            sha256=*)     sha256="${kv#*=}" ;;
        esac
    done
    python3 - <<EOF
import json, os
mp = "${meta}"; data = {}
if os.path.exists(mp):
    try: data = json.load(open(mp))
    except: pass
data.update({"type":"${ZBM_TYPE}","system":"${ZBM_SYSTEM}","label":"${ZBM_LABEL}",
    "date":"${ZBM_DATE}","built":"${built}","kernel_ver":"${kernel_ver}",
    "init_type":"${init_type}","size_bytes":${size_bytes},
    "sha256":"${sha256}","builder":"${builder}"})
with open(mp,'w') as f: json.dump(data,f,indent=2); f.write('\n')
print(f"  Meta: {os.path.basename(mp)}")
EOF
}

zbm_read_meta() {
    local meta; meta=$(zbm_meta "$1")
    [[ -f "$meta" ]] || return 1
    python3 -c "import json; d=json.load(open('${meta}')); print(d.get('${2}',''))" 2>/dev/null
}

# Appelé depuis coherence.sh --check-orphans
zbm_check_orphans() {
    local BOOT="${BOOT:-/boot}"
    for dir in "$BOOT/images/kernels" "$BOOT/images/initramfs" \
               "$BOOT/images/modules" "$BOOT/images/rootfs" \
               "$BOOT/images/startup" "$BOOT/images/failsafe"; do
        [[ -d "$dir" ]] || continue
        for f in "$dir"/*; do
            [[ -f "$f" ]] && [[ "$f" != *.meta ]] || continue
            zbm_validate_name "$f" || echo "$f"
        done
    done
}

# Appelé depuis initramfs.sh et coherence.sh pour détecter le type initramfs
zbm_init_type() {
    local p; p=$(zbm_parse "$1") || { echo "unknown"; return; }
    eval "$p"
    case "$ZBM_LABEL" in
        zbm)        echo "zbm" ;;
        zbm-stream) echo "zbm-stream" ;;
        minimal)    echo "minimal" ;;
        custom-*)   echo "custom" ;;
        *)
            local it; it=$(zbm_read_meta "$1" "init_type" 2>/dev/null || true)
            echo "${it:-unknown}" ;;
    esac
}

# =============================================================================
# zbm_select_kernel [--allow-new] [--label <label>] [--quiet]
#
# Affiche la liste des kernels installes dans boot_pool avec leurs meta
# (label, date, kver, taille, modules associes).
# Propose de choisir parmi eux via un menu numerote.
#
# Options :
#   --allow-new   : ajoute l'option "installer un nouveau kernel"
#   --label <l>   : pre-selectionne ce label si present (defaut si existant)
#   --quiet       : pas d'affichage interactif, retourne le plus recent
#
# Sortie stdout  : "<path>|<label>|<date>|<kver>"
#                   ou "new||"  si l'utilisateur choisit d'installer un nouveau
# Return code    : 0 = selection valide, 1 = annule / aucun kernel
#
# Exemples :
#   SEL=$(zbm_select_kernel --allow-new)
#   IFS='|' read -r KPATH KLABEL KDATE KVER <<< "$SEL"
#   [[ "$SEL" == "new"* ]] && echo "installer un nouveau kernel"
# =============================================================================
zbm_select_kernel() {
    local ALLOW_NEW=0 PREFILL_LABEL="" QUIET=0
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --allow-new) ALLOW_NEW=1;          shift ;;
            --label)     PREFILL_LABEL="$2";   shift 2 ;;
            --quiet)     QUIET=1;              shift ;;
            *)           shift ;;
        esac
    done

    local dir; dir=$(zbm_dir kernel)
    local mdir; mdir=$(zbm_dir modules)

    # Collecter tous les kernels installes (non-failsafe, non-.meta)
    declare -a K_PATHS=() K_LABELS=() K_DATES=() K_KVERS=() K_SIZES=() K_HAS_MOD=()

    for f in "$dir"/kernel-*; do
        [[ -f "$f" ]] && [[ "$f" != *.meta ]] || continue
        local p; p=$(zbm_parse "$f") || continue
        eval "$p"
        [[ "$ZBM_SYSTEM" == "failsafe" ]] && continue
        local kv; kv=$(zbm_read_meta "$f" "kernel_ver" 2>/dev/null || true)
        local sz; sz=$(du -sh "$f" 2>/dev/null | cut -f1 || echo "?")
        local has_mod=0
        [[ -f "$mdir/modules-${ZBM_LABEL}-${ZBM_DATE}.sfs" ]] && has_mod=1
        K_PATHS+=("$f")
        K_LABELS+=("$ZBM_LABEL")
        K_DATES+=("$ZBM_DATE")
        K_KVERS+=("${kv:-?}")
        K_SIZES+=("$sz")
        K_HAS_MOD+=("$has_mod")
    done

    # Aucun kernel
    if [[ ${#K_PATHS[@]} -eq 0 ]]; then
        if [[ $ALLOW_NEW -eq 1 ]]; then
            [[ $QUIET -eq 0 ]] && echo "  (aucun kernel installe)" >&2
            echo "new||"
            return 0
        fi
        [[ $QUIET -eq 0 ]] && echo "  Aucun kernel dans boot_pool" >&2
        return 1
    fi

    # Mode silencieux : retourner le plus recent
    if [[ $QUIET -eq 1 ]]; then
        # Trier par date decroissante, prendre le premier
        local best_idx=0
        for i in "${!K_DATES[@]}"; do
            [[ "${K_DATES[$i]}" > "${K_DATES[$best_idx]}" ]] && best_idx="$i"
        done
        echo "${K_PATHS[$best_idx]}|${K_LABELS[$best_idx]}|${K_DATES[$best_idx]}|${K_KVERS[$best_idx]}"
        return 0
    fi

    # Identifier le kernel actif (symlink vmlinuz)
    local ACTIVE_PATH=""
    # vmlinuz est à la RACINE de BOOT, pas dans images/
    local vmlinuz="${BOOT:-/boot}/vmlinuz"
    [[ -L "$vmlinuz" ]] && ACTIVE_PATH=$(readlink -f "$vmlinuz" 2>/dev/null || true)

    # Un seul kernel et pas de --allow-new : confirmation rapide
    if [[ ${#K_PATHS[@]} -eq 1 ]] && [[ $ALLOW_NEW -eq 0 ]]; then
        local marker=""; [[ "${K_PATHS[0]}" == "$ACTIVE_PATH" ]] && marker=" [actif]"
        echo "" >&2
        echo "  Kernel installe : kernel-${K_LABELS[0]}-${K_DATES[0]}  kver=${K_KVERS[0]}${marker}" >&2
        [[ ${K_HAS_MOD[0]} -eq 1 ]] && echo "    + modules-${K_LABELS[0]}-${K_DATES[0]}.sfs" >&2
        echo "${K_PATHS[0]}|${K_LABELS[0]}|${K_DATES[0]}|${K_KVERS[0]}"
        return 0
    fi

    # Menu numerote
    echo "" >&2
    echo "  Kernels installes dans boot_pool :" >&2
    echo "" >&2

    local DEFAULT_IDX=0
    for i in "${!K_PATHS[@]}"; do
        local num=$((i+1))
        local active_mark=""
        [[ "${K_PATHS[$i]}" == "$ACTIVE_PATH" ]] && active_mark=" [actif]"
        local pre_mark=""
        [[ "${K_LABELS[$i]}" == "$PREFILL_LABEL" ]] && {
            pre_mark=" [actuel config.sh]"
            DEFAULT_IDX=$num
        }
        printf "    %2d)  kernel-%-34s  kver=%-20s  %s%s%s\n" \
            "$num" \
            "${K_LABELS[$i]}-${K_DATES[$i]}" \
            "${K_KVERS[$i]}" \
            "${K_SIZES[$i]}" \
            "$active_mark" \
            "$pre_mark" >&2
        if [[ ${K_HAS_MOD[$i]} -eq 1 ]]; then
            local msz; msz=$(du -sh "$mdir/modules-${K_LABELS[$i]}-${K_DATES[$i]}.sfs" 2>/dev/null | cut -f1 || echo "?")
            printf "          + modules-%-28s  %s\n" \
                "${K_LABELS[$i]}-${K_DATES[$i]}.sfs" "$msz" >&2
        fi
    done

    if [[ $ALLOW_NEW -eq 1 ]]; then
        printf "    %2d)  [installer un nouveau kernel depuis le live]\n" \
            "$((${#K_PATHS[@]}+1))" >&2
    fi

    echo "" >&2

    local MAX=$((${#K_PATHS[@]} + (ALLOW_NEW == 1 ? 1 : 0)))
    local PROMPT="  Choix [1-${MAX}"
    [[ $DEFAULT_IDX -gt 0 ]] && PROMPT+=", defaut=${DEFAULT_IDX}"
    PROMPT+=", 0=annuler] : "
    echo -n "$PROMPT" >&2
    read -r _IDX

    # Defaut si entree vide
    [[ -z "$_IDX" && $DEFAULT_IDX -gt 0 ]] && _IDX="$DEFAULT_IDX"

    if [[ "$_IDX" =~ ^[0-9]+$ ]]; then
        # Annuler
        [[ "$_IDX" -eq 0 ]] && return 1
        # "Installer un nouveau kernel"
        if [[ $ALLOW_NEW -eq 1 ]] && (( _IDX == ${#K_PATHS[@]}+1 )); then
            echo "new||"
            return 0
        fi
        # Kernel existant
        if (( _IDX >= 1 && _IDX <= ${#K_PATHS[@]} )); then
            local idx=$((_IDX-1))
            echo "${K_PATHS[$idx]}|${K_LABELS[$idx]}|${K_DATES[$idx]}|${K_KVERS[$idx]}"
            return 0
        fi
    fi

    echo "  Choix invalide" >&2
    return 1
}
