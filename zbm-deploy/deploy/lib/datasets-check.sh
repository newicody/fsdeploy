#!/bin/bash
# =============================================================================
# lib/datasets-check.sh — Vérification et création des datasets ZFS
#
# ARCHITECTURE ZFS du projet :
#
#   boot_pool     → /boot      (NVMe-A, partition ZFS)
#   fast_pool     → datasets par système (NVMe-B entier)
#   data_pool     → home + archives (SATA RAIDZ2)
#
# ARCHITECTURE OVERLAY (invariant clé) :
#   Chaque système = 1 seul dataset : fast_pool/overlay-<s>
#   lower  = rootfs.sfs (squashfs ro) — contient /var /tmp /etc ...
#   upper  = fast_pool/overlay-<s>/upper  (rw, persistant)
#   merged = overlayfs → pivot_root
#
#   Aucun dataset ZFS séparé pour /var, /var/log, /tmp.
#   /home = data_pool/home (partagé, monté par initramfs)
#
# ÉTAT INITIAL :
#   Au déploiement : seul boot_pool/images est indispensable.
#   fast_pool/overlay-<s> peut être créé maintenant ou au premier boot.
#
# Usage :
#   bash lib/datasets-check.sh             # vérifier + proposer création
#   bash lib/datasets-check.sh --initial   # datasets minimum pour 1er boot
#   bash lib/datasets-check.sh --full      # architecture complète
#   bash lib/datasets-check.sh --system systeme2  # ajouter un système
# =============================================================================

set -euo pipefail

_MOUNTS_SH="${SCRIPT_DIR}/mounts.sh"
[[ -f "$_MOUNTS_SH" ]] && source "$_MOUNTS_SH"


SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

GREEN='\033[1;32m'; YELLOW='\033[1;33m'; RED='\033[1;31m'
CYAN='\033[1;36m'; BOLD='\033[1m'; DIM='\033[2m'; NC='\033[0m'
ok()    { echo -e "  ${GREEN}✅${NC} $*"; }
miss()  { echo -e "  ${YELLOW}◌ ${NC} $*"; }
err_ln(){ echo -e "  ${RED}❌${NC} $*"; }
warn()  { echo -e "  ${YELLOW}⚠ ${NC} $*"; }
info()  { echo -e "  ${DIM}   $*${NC}"; }
section(){ echo -e "\n${BOLD}── $* ──${NC}"; }

MODE="check"     # check | initial | full
ADD_SYSTEM=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --initial) MODE="initial"; shift ;;
        --full)    MODE="full";    shift ;;
        --system)  MODE="system"; ADD_SYSTEM="$2"; shift 2 ;;
        *) echo "Usage: $0 [--initial|--full|--system <name>]"; exit 1 ;;
    esac
done

# Source naming.sh pour zbm_ensure_images_dataset, zbm_dir, etc.
_NAMING="${SCRIPT_DIR}/naming.sh"
[[ -f "$_NAMING" ]] && source "$_NAMING" || true

# ─── Montage temporaire de boot_pool (si pas déjà monté) ────────────────────
# Nécessaire pour zbm_ensure_images_dataset et pour les checks "Structure boot_pool".
_DS_BOOT_MOUNTED=0
_ensure_boot_mounted() {
    # Priorité 1 : BOOT déjà défini et monté
    if [[ -n "${BOOT:-}" ]] && mountpoint -q "${BOOT}" 2>/dev/null; then return 0; fi
    # Priorité 2 : boot_pool déjà monté quelque part selon ZFS
    local _cur
    _cur=$(zfs mount 2>/dev/null | awk '$1=="boot_pool"{print $2}' | head -1 || true)
    if [[ -n "$_cur" ]]; then BOOT="$_cur"; export BOOT; return 0; fi
    # Priorité 3 : importer et monter sur $ZBM_BOOT (= /mnt/zbm/boot, JAMAIS tmp aléatoire)
    if ! zpool list boot_pool >/dev/null 2>&1; then
        zpool import -N boot_pool 2>/dev/null || return 1
    fi
    BOOT="${ZBM_BOOT:-/mnt/zbm/boot}"
    mkdir -p "$BOOT"
    if mount -t zfs boot_pool "$BOOT" 2>/dev/null; then
        _DS_BOOT_MOUNTED=1; export BOOT _DS_BOOT_MOUNTED; return 0
    fi
    BOOT=""; return 1
}
_cleanup_boot_ds() {
    [[ "${_DS_BOOT_MOUNTED:-0}" -eq 1 ]] || return 0
    # boot_pool/images AVANT boot_pool
    zfs unmount boot_pool/images 2>/dev/null || true
    umount "${BOOT:-}" 2>/dev/null || true
    _DS_BOOT_MOUNTED=0
}
trap _cleanup_boot_ds EXIT

# Initialiser la structure images/* dès maintenant (idempotent, silencieux si OK)
if zpool list boot_pool >/dev/null 2>&1; then
    _ensure_boot_mounted && zbm_ensure_images_dataset 2>/dev/null || true
fi

# =============================================================================
# DÉFINITION DE L'ARCHITECTURE
# =============================================================================

# Datasets TOUJOURS requis (indépendants des systèmes)
# Architecture minimale :
#   boot_pool/images  : stockage des kernels, initramfs, rootfs, modules (mountpoint=legacy)
#   data_pool/home    : répertoires utilisateurs partagés
#   Par systeme : fast_pool/overlay-<s> + var-<s> + log-<s> + tmp-<s>
#   Failsafe    : fast_pool/overlay-failsafe + var-failsafe + log-failsafe
#   Archives    : data_pool/archives/<s>  (optionnel, cold storage)
# Datasets nécessaires au DÉPLOIEMENT seulement (pas au runtime) :
#   boot_pool/images : stockage des images (kernels, initramfs, rootfs, modules)
# Les datasets runtime (overlay, home, archives) sont optionnels au deploy —
# ils seront créés/montés par l'initramfs au premier boot.
declare -a ARCH_BASE=(
    "boot_pool/images|inherited|boot_pool|Stockage images (kernels, initramfs, rootfs, modules)"
)
# data_pool/home : monté par initramfs au boot, pas requis au déploiement
# Mais on le vérifie/crée si data_pool est disponible (optionnel)
declare -a ARCH_OPTIONAL=(
    "data_pool/home|/home|data_pool|Répertoires utilisateurs partagés"
)

# Datasets PAR SYSTÈME — générés dynamiquement selon les systèmes connus
arch_for_system() {
    local sys="$1"
    # Un seul dataset par système : l'upper de l'OverlayFS.
    # Architecture :
    #   lower  = rootfs.sfs (ro) — contient déjà /var /tmp /etc ...
    #   upper  = fast_pool/overlay-<s> (rw) — toutes les écritures vont ici
    #   merged = overlayfs → pivot_root
    #
    # /var /tmp /run sont dans le lower et redirigés vers l'upper automatiquement.
    # Aucun dataset ZFS séparé pour /var, /var/log ou /tmp.
    echo "fast_pool/overlay-${sys}|none|fast_pool|Upper OverlayFS du systeme ${sys} (canmount=noauto)"
    # data_pool/archives/<s> est optionnel (cold storage) — créez manuellement si besoin
}

# Archives optionnelles par systeme (cold storage)
arch_archives_for_system() {
    local sys="$1"
    echo "data_pool/archives/${sys}|none|data_pool|Archives snapshots ${sys} (optionnel)"
}

# Détecter les systèmes : source de vérité = SYSTEMS dans config.sh
# Fallback : datasets fast_pool/var-* existants
detect_systems() {
    local -a systems=()
    local CONF

    # 1. Lire SYSTEMS depuis config.sh (source de vérité)
    CONF="$(dirname "$(dirname "$0")")/config.sh"
    if [[ -f "$CONF" ]]; then
        local _raw
        _raw=$(env CONF="$CONF" bash -c 'source "$CONF" 2>/dev/null; printf "%s\n" "${SYSTEMS[@]:-}"' 2>/dev/null || true)
        while IFS= read -r s; do
            [[ -n "$s" ]] && systems+=("$s")
        done <<< "$_raw"
    fi

    # 2. Fallback : datasets fast_pool/overlay-* existants non encore dans la liste
    #    (overlay-* est le seul dataset par système depuis l'abandon de var/log/tmp)
    if zpool list fast_pool >/dev/null 2>&1; then
        while IFS= read -r ds; do
            local sysname="${ds#fast_pool/overlay-}"
            [[ -z "$sysname" || "$sysname" == "failsafe" ]] && continue
            local found=0
            for s in "${systems[@]:-}"; do [[ "$s" == "$sysname" ]] && found=1; done
            [[ $found -eq 0 ]] && systems+=("$sysname")
        done < <(zfs list -H -o name fast_pool 2>/dev/null | grep '^fast_pool/overlay-' || true)
    fi

    # 3. Par défaut si rien trouvé
    [[ ${#systems[@]} -eq 0 ]] && systems=("systeme1")

    printf '%s\n' "${systems[@]}"
}

# =============================================================================
# AFFICHAGE D'UN DATASET
# =============================================================================
show_dataset() {
    local ds="$1" mp="$2" pool="$3"
    if ! zpool list "$pool" >/dev/null 2>&1; then
        miss "$(printf '%-40s' "$ds")  ${YELLOW}[$pool non importé]${NC}"
        return 1
    fi
    if zfs list "$ds" >/dev/null 2>&1; then
        local ACTUAL_MP USED COMPRESS CANMOUNT
        ACTUAL_MP=$(zfs get -H -o value mountpoint "$ds" 2>/dev/null | xargs)
        USED=$(zfs get -H -o value used "$ds" 2>/dev/null | xargs)
        COMPRESS=$(zfs get -H -o value compression "$ds" 2>/dev/null | xargs)
        CANMOUNT=$(zfs get -H -o value canmount "$ds" 2>/dev/null | xargs)
        local mp_status="" cm_warn=""
        # boot_pool/images : mountpoint hérité — vérifier seulement qu'il n'est pas legacy
        if [[ "$ds" == "boot_pool/images" ]]; then
            [[ "$ACTUAL_MP" != "legacy" && "$ACTUAL_MP" != "none" ]] \
                && mp_status="✓ (inherited: $ACTUAL_MP)" \
                || mp_status="⚠ mountpoint=${ACTUAL_MP} (devrait être hérité de boot_pool)"
        else
            [[ "$ACTUAL_MP" == "$mp" ]] && mp_status="✓" || mp_status="⚠ actual=$ACTUAL_MP"
        fi
        # fast_pool/overlay-* DOIT avoir canmount=noauto (protection anti-corruption overlay)
        if [[ "$ds" == fast_pool/overlay-* && "$CANMOUNT" != "noauto" ]]; then
            cm_warn="  ${YELLOW}⚠ canmount=${CANMOUNT} (doit être noauto pour overlay)${NC}"
        fi
        ok "$(printf '%-40s' "$ds")  mp=${ACTUAL_MP} ${mp_status}  used=${USED}  comp=${COMPRESS}${cm_warn}"
        return 0
    else
        miss "$(printf '%-40s' "$ds")  → à créer"
        return 1
    fi
}

# =============================================================================
# CRÉATION D'UN DATASET
# =============================================================================
create_dataset() {
    local ds="$1" mp="$2"
    local pool="${ds%%/*}"
    if ! zpool list "$pool" >/dev/null 2>&1; then
        echo -e "  ${RED}❌ ${pool} non disponible — création impossible${NC}"
        return 1
    fi
    # Créer le parent si nécessaire
    local parent="${ds%/*}"
    if [[ "$parent" != "$pool" ]] && ! zfs list "$parent" >/dev/null 2>&1; then
        echo -e "  ${CYAN}   Création parent : $parent${NC}"
        zfs create -o compression=zstd -o atime=off -o canmount=noauto -o mountpoint=none "$parent" \
            && ok "Créé (parent) : $parent" \
            || err_ln "Échec parent : $parent"
    fi

    # Choisir les options selon le dataset
    local EXTRA_OPTS=""
    if [[ "$ds" == fast_pool/overlay-* ]]; then
        # overlay-<s> : canmount=noauto, mountpoint=none
        # L'initramfs monte ce dataset comme upper OverlayFS via zbm_overlay=
        # Jamais monté automatiquement par ZFS (risque de corruption overlay si double-montage)
        EXTRA_OPTS="-o canmount=noauto -o mountpoint=none"
    elif [[ "$ds" == fast_pool/* ]]; then
        EXTRA_OPTS="-o canmount=noauto"
    fi

    # boot_pool/images : enfant ZFS normal de boot_pool, mountpoint hérité (pas legacy)
    # compression=lz4 mieux adapté aux gros fichiers binaires (kernels, sfs)
    local COMPRESS="zstd"
    local MP_OPT="-o mountpoint=${mp}"
    if [[ "$ds" == "boot_pool/images" ]]; then
        COMPRESS="lz4"
        # Pas de mountpoint explicite : héritage ZFS → $BOOT/images automatiquement
        # quand boot_pool est monté. "zfs mount boot_pool/images" sera appelé par
        # zbm_ensure_images_dataset après chaque montage de boot_pool.
        MP_OPT=""
    fi

    zfs create -o compression="$COMPRESS" -o atime=off \
        ${MP_OPT} ${EXTRA_OPTS} "$ds" \
        && ok "Créé : $ds${MP_OPT:+  (mp=${mp})}${EXTRA_OPTS:+  canmount=noauto}" \
        || { err_ln "Échec : $ds"; return 1; }

    # boot_pool/images : monter immédiatement et créer les sous-dossiers
    if [[ "$ds" == "boot_pool/images" ]]; then
        zbm_ensure_images_dataset 2>&1 | sed 's/^/  /' || true
    fi
}

# =============================================================================
# MODE : initial — minimum pour premier boot
# =============================================================================
do_initial() {
    section "Datasets minimum pour le premier boot"
    echo -e "  ${DIM}À ce stade, aucun système/rootfs n'est encore défini.${NC}"
    echo -e "  ${DIM}Le premier boot utilise un kernel générique + initramfs minimal.${NC}"
    echo ""
    local -a MISSING=()
    for entry in "${ARCH_BASE[@]}"; do
        IFS='|' read -r ds mp pool desc <<< "$entry"
        show_dataset "$ds" "$mp" "$pool" || MISSING+=("${ds}|${mp}|${pool}")
        info "$desc"
    done
    if [[ ${#MISSING[@]} -gt 0 ]]; then
        echo ""
        echo -e "  ${CYAN}Datasets à créer :${NC}"
        for t in "${MISSING[@]}"; do
            IFS='|' read -r ds mp pool <<< "$t"
            local _cm=""; [[ "$ds" == fast_pool/* ]] && _cm=" -o canmount=noauto"
            echo -e "  ${CYAN}  zfs create -o compression=zstd -o atime=off${_cm} -o mountpoint=${mp} ${ds}${NC}"
        done
        echo ""
        echo -n "  Créer maintenant ? [o/N] : "
        read -r DO_CREATE
        if [[ "$DO_CREATE" =~ ^[Oo]$ ]]; then
            for t in "${MISSING[@]}"; do
                IFS='|' read -r ds mp pool <<< "$t"
                create_dataset "$ds" "$mp"
            done
        fi
    else
        ok "Datasets de base présents — premier boot possible"
    fi
    echo ""
    warn "Pour ajouter un système : bash lib/datasets-check.sh --system <nom>"
}

# =============================================================================
# MODE : full — architecture complète avec systèmes détectés
# =============================================================================
do_full() {
    section "Architecture complète"

    local -a ALL_MISSING=()

    # Base
    echo -e "  ${BOLD}Datasets de base :${NC}"
    for entry in "${ARCH_BASE[@]}"; do
        IFS='|' read -r ds mp pool desc <<< "$entry"
        show_dataset "$ds" "$mp" "$pool" || ALL_MISSING+=("${ds}|${mp}|${pool}")
    done

    # Par système
    local -a SYSTEMS=()
    while IFS= read -r s; do SYSTEMS+=("$s"); done < <(detect_systems)

    if [[ ${#SYSTEMS[@]} -eq 0 ]]; then
        echo ""
        warn "Aucun système détecté. Utilisez --system <nom> pour en ajouter un."
    else
        echo ""
        echo -e "  ${BOLD}Datasets par système :${NC}"
        for sys in "${SYSTEMS[@]}"; do
            echo -e "  ${DIM}  ── ${sys} ──${NC}"
            while IFS= read -r entry; do
                IFS='|' read -r ds mp pool desc <<< "$entry"
                show_dataset "$ds" "$mp" "$pool" || ALL_MISSING+=("${ds}|${mp}|${pool}")
            done < <(arch_for_system "$sys")
        done
    fi

    # Failsafe
    echo ""
    echo -e "  ${BOLD}Datasets failsafe :${NC}"
    while IFS= read -r entry; do
        IFS='|' read -r ds mp pool desc <<< "$entry"
        show_dataset "$ds" "$mp" "$pool" || ALL_MISSING+=("${ds}|${mp}|${pool}")
    done < <(arch_for_system "failsafe")

    if [[ ${#ALL_MISSING[@]} -gt 0 ]]; then
        echo ""
        section "Datasets manquants"
        for t in "${ALL_MISSING[@]}"; do
            IFS='|' read -r ds mp pool <<< "$t"
            local _cm=""; [[ "$ds" == fast_pool/* ]] && _cm=" -o canmount=noauto"
            echo -e "  ${CYAN}zfs create -o compression=zstd -o atime=off -o mountpoint=${mp}${_cm} ${ds}${NC}"
        done
        echo ""
        echo -n "  Créer les datasets manquants ? [o/N] : "
        read -r DO_CREATE
        if [[ "$DO_CREATE" =~ ^[Oo]$ ]]; then
            for t in "${ALL_MISSING[@]}"; do
                IFS='|' read -r ds mp pool <<< "$t"
                create_dataset "$ds" "$mp"
            done
        fi
    else
        ok "Tous les datasets sont présents"
    fi
}

# =============================================================================
# MODE : system — ajouter les datasets d'un nouveau système
# =============================================================================
do_add_system() {
    local sys="$1"
    section "Ajout du système : $sys"
    echo -e "  ${YELLOW}⚠️  Cette opération va créer des datasets ZFS pour le système '${sys}'.${NC}"
    echo -n "  Confirmer ? [o/N] : "
    read -r CONFIRM
    [[ "$CONFIRM" =~ ^[Oo]$ ]] || { echo "  Annulé."; exit 0; }

    local -a MISSING=()
    while IFS= read -r entry; do
        IFS='|' read -r ds mp pool desc <<< "$entry"
        show_dataset "$ds" "$mp" "$pool" || MISSING+=("${ds}|${mp}|${pool}")
    done < <(arch_for_system "$sys")

    for t in "${MISSING[@]}"; do
        IFS='|' read -r ds mp pool <<< "$t"
        create_dataset "$ds" "$mp"
    done
    ok "Système '${sys}' prêt — lancez lib/rootfs.sh pour ajouter un rootfs"
}

# =============================================================================
# MODE : check — afficher l'état, ne rien créer
# =============================================================================
do_check() {
    section "État des datasets ZFS"
    do_full
    echo ""
    section "Structure boot_pool"
    if ! zpool list boot_pool >/dev/null 2>&1; then
        warn "boot_pool non disponible"
        return
    fi
    # Réutiliser _ensure_boot_mounted défini en haut (et le trap EXIT global)
    if ! _ensure_boot_mounted; then
        warn "Impossible de monter boot_pool"
        return
    fi
    # Créer/monter boot_pool/images si absent (idempotent)
    zbm_ensure_images_dataset 2>&1 | grep -v "^$" | sed 's/^/  /' || true

    # Statut du dataset boot_pool/images
    echo ""
    echo -e "  ${BOLD}Dataset boot_pool/images :${NC}"
    if zfs list boot_pool/images >/dev/null 2>&1; then
        local _img_mp; _img_mp=$(zfs get -H -o value mountpoint boot_pool/images 2>/dev/null)
        local _img_used; _img_used=$(zfs get -H -o value used boot_pool/images 2>/dev/null)
        if mountpoint -q "$BOOT/images" 2>/dev/null; then
            ok "$(printf '%-40s' "boot_pool/images")  mp=${_img_mp}  used=${_img_used}  monté ✓"
        else
            warn "boot_pool/images existe (mp=${_img_mp}) mais non monté sur $BOOT/images"
        fi
    else
        miss "boot_pool/images  → absent (lancez datasets-check.sh --initial)"
    fi

    # Sous-dossiers dans boot_pool/images
    echo ""
    echo -e "  ${BOLD}Contenu images/* :${NC}"
    local -a BOOT_DIRS=(
        "images/kernels" "images/initramfs" "images/modules"
        "images/rootfs" "images/startup" "images/failsafe"
    )
    for d in "${BOOT_DIRS[@]}"; do
        if [[ -d "$BOOT/$d" ]]; then
            local cnt; cnt=$(find "$BOOT/$d" -maxdepth 1 -not -name '*.meta' 2>/dev/null | wc -l)
            ok "$(printf '%-32s' "$BOOT/$d")  ($((cnt-1)) fichier(s))"
        else
            miss "$BOOT/$d"
        fi
    done

    # Autres répertoires dans boot_pool (simples dossiers, pas des datasets)
    echo ""
    echo -e "  ${BOLD}Autres répertoires boot_pool :${NC}"
    for d in "presets" "snapshots" "hooks" "efi/EFI/ZBM"; do
        if [[ -d "$BOOT/$d" ]]; then
            local cnt2; cnt2=$(find "$BOOT/$d" -maxdepth 1 2>/dev/null | wc -l)
            ok "$(printf '%-32s' "$BOOT/$d")  ($((cnt2-1)) fichier(s))"
        else
            miss "$BOOT/$d"
        fi
    done

    # Symlinks
    echo ""
    echo -e "  ${BOLD}Symlinks actifs :${NC}"
    for link in vmlinuz initrd.img modules.sfs rootfs.sfs; do
        local lp="$BOOT/$link"
        if [[ -L "$lp" ]]; then
            local tgt; tgt=$(readlink "$lp")
            local state; state=$([[ -e "$lp" ]] && echo "✅" || echo "❌ cible manquante")
            ok "$(printf '%-18s' "$link") → $(basename "$tgt")  $state"
        else
            miss "$(printf '%-18s' "$link") → non défini"
        fi
    done

    echo ""
    echo -e "  ${BOLD}Kernels disponibles :${NC}"
    local found_k=0
    for f in "$BOOT/images/kernels"/kernel-*; do
        [[ -f "$f" ]] && [[ "$f" != *.meta ]] || continue
        echo "    $(basename "$f")"; found_k=1
    done
    [[ $found_k -eq 0 ]] && warn "Aucun kernel — lancez lib/kernel.sh"

    echo -e "  ${BOLD}Initramfs disponibles :${NC}"
    local found_i=0
    for f in "$BOOT/images/initramfs"/initramfs-*; do
        [[ -f "$f" ]] && [[ "$f" != *.meta ]] || continue
        echo "    $(basename "$f")"; found_i=1
    done
    [[ $found_i -eq 0 ]] && warn "Aucun initramfs — lancez lib/initramfs.sh"

    echo -e "  ${BOLD}Rootfs disponibles :${NC}"
    local found_rootfs=0
    for f in "$BOOT/images/rootfs"/rootfs-*; do
        [[ -f "$f" ]] && [[ "$f" != *.meta ]] || continue
        echo "    $(basename "$f")"; found_rootfs=1
    done
    [[ $found_rootfs -eq 0 ]] && info "Aucun rootfs — normal pour un premier déploiement"
}

# =============================================================================
case "$MODE" in
    initial) do_initial ;;
    full)    do_full ;;
    system)  do_add_system "$ADD_SYSTEM" ;;
    check)   do_check ;;
esac
