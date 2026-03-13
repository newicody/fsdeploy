#!/bin/bash
# =============================================================================
# deploy.sh — Déploiement initial depuis Debian live trixie
#
# Prérequis :
#   - Disques partitionnés manuellement (EFI + ZFS sur NVMe-A)
#   - Pools ZFS créés manuellement (boot_pool, fast_pool, data_pool)
#   - Le rootfs Gentoo (.sfs) est présent :
#       · soit dans boot_pool/images/rootfs/
#       · soit sur une clé USB
#
# Ce script :
#   1. Détecte l'environnement (NVMe, EFI existante, pools, datasets)
#   2. Liste les datasets manquants et propose de les créer
#   3. Installe le rootfs, construit python.sfs, l'initramfs, ZFSBootMenu
#   4. Génère les presets et le failsafe
#
# Usage : bash deploy.sh
# =============================================================================

set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB="$SCRIPT_DIR/lib"
CONFIG_FILE="$SCRIPT_DIR/config.sh"

# Source de vérité pour les points de montage (avant tout autre source)
[[ -f "$LIB/mounts.sh" ]] && source "$LIB/mounts.sh"
# naming.sh contient zbm_locate_boot() et zbm_cleanup_boot()
[[ -f "$LIB/naming.sh" ]] && source "$LIB/naming.sh"

RED='\033[1;31m'; GREEN='\033[1;32m'; YELLOW='\033[1;33m'
BLUE='\033[1;34m'; CYAN='\033[1;36m'; BOLD='\033[1m'; NC='\033[0m'

ok()    { echo -e "  ${GREEN}✅ $*${NC}"; }
warn()  { echo -e "  ${YELLOW}⚠️  $*${NC}"; }
err()   { echo -e "  ${RED}❌ $*${NC}"; exit 1; }
step()  { echo -e "\n${BLUE}${BOLD}══ $* ══${NC}"; }

[[ $EUID -ne 0 ]] && err "Root requis."
[[ ! -d "$LIB" ]] && err "Répertoire lib/ introuvable : $LIB"

# =============================================================================
# INSTALL PAQUETS
# =============================================================================
install_packages() {
    step "Installation des dépendances Debian live"
    apt-get update -qq
    apt-get install -y --no-install-recommends \
        zfsutils-linux \
        dracut dracut-core \
        squashfs-tools zstd xz-utils \
        efibootmgr dosfstools \
        python3 python3-pip python3-venv \
        ffmpeg \
        wget curl rsync gdisk \
        2>/dev/null
    ok "Paquets installés"
}

# =============================================================================
# CONFIGURATION COMPLÉMENTAIRE (rootfs_label, kernel_ver, stream_key)
# =============================================================================
configure_extra() {
    [[ -f "$CONFIG_FILE" ]] && source "$CONFIG_FILE"

    echo ""
    echo -e "${BOLD}Configuration complémentaire${NC}"
    echo ""
    echo -n "  Label rootfs (ex: gentoo-6.19) [${ROOTFS_LABEL:-gentoo}] : "
    read -r v; [[ -n "$v" ]] && ROOTFS_LABEL="$v"
    ROOTFS_LABEL="${ROOTFS_LABEL:-gentoo}"

    echo -n "  Version kernel (ex: 6.6.47-gentoo) [${KERNEL_VER:-auto}] : "
    read -r v; [[ -n "$v" ]] && KERNEL_VER="$v"
    KERNEL_VER="${KERNEL_VER:-auto}"

    echo -n "  Clé stream YouTube (vide = plus tard) [${STREAM_KEY:-}] : "
    read -r v; [[ -n "$v" ]] && STREAM_KEY="$v"
    STREAM_KEY="${STREAM_KEY:-}"

    # Mettre à jour deploy.conf
    if [[ -f "$CONFIG_FILE" ]]; then
        sed -i "s|^ROOTFS_LABEL=.*|ROOTFS_LABEL=\"${ROOTFS_LABEL}\"|" "$CONFIG_FILE"
        sed -i "s|^KERNEL_VER=.*|KERNEL_VER=\"${KERNEL_VER}\"|"       "$CONFIG_FILE"
        sed -i "s|^STREAM_KEY=.*|STREAM_KEY=\"${STREAM_KEY}\"|"       "$CONFIG_FILE"
    fi
    ok "Configuration mise à jour"
}

# =============================================================================
# MONTAGE DE boot_pool + boot_pool/images — étape 0 obligatoire
#
# boot_pool a mountpoint=legacy → ZFS ne le monte JAMAIS automatiquement.
# Il faut :
#   1. zpool import boot_pool  (si pas déjà importé)
#   2. mount -t zfs boot_pool $ZBM_BOOT  (montage explicite)
#   3. zfs mount boot_pool/images          (dataset enfant)
#
# Seuls ces deux datasets sont nécessaires pour le déploiement.
# fast_pool et data_pool ne sont PAS montés ici (c'est le rôle de l'initramfs).
# =============================================================================
mount_boot_pool() {
    local target="${ZBM_BOOT:-/mnt/zbm/boot}"

    # Déjà monté ? Récupérer le chemin depuis ZFS
    local cur_mp
    cur_mp=$(zfs mount 2>/dev/null | awk '$1=="boot_pool"{print $2}' | head -1 || true)
    if [[ -n "$cur_mp" ]] && mountpoint -q "$cur_mp" 2>/dev/null; then
        BOOT="$cur_mp"; export BOOT
        ok "boot_pool déjà monté → $BOOT"
        _mount_images_dataset
        return 0
    fi

    # Importer si nécessaire
    if ! zpool list boot_pool >/dev/null 2>&1; then
        step "Import boot_pool"
        # Attendre que les périphériques soient disponibles
        local wait=0
        until ls /dev/disk/by-id/ >/dev/null 2>&1 || [[ $wait -ge 10 ]]; do
            sleep 1; wait=$((wait+1))
        done
        if ! zpool import -N boot_pool 2>/dev/null; then
            zpool import -f -N boot_pool 2>/dev/null                 || err "boot_pool introuvable — vérifiez le câblage NVMe-A"
        fi
        ok "boot_pool importé"
    fi

    # Monter boot_pool sur $ZBM_BOOT (= /mnt/zbm/boot)
    BOOT="$target"
    mkdir -p "$BOOT"
    if ! mount -t zfs boot_pool "$BOOT" 2>/dev/null; then
        # boot_pool peut déjà être partiellement monté — essayer de récupérer
        cur_mp=$(zfs mount 2>/dev/null | awk '$1=="boot_pool"{print $2}' | head -1 || true)
        if [[ -n "$cur_mp" ]]; then
            BOOT="$cur_mp"; export BOOT
            warn "boot_pool monté sur $BOOT (pas $target)"
        else
            err "Impossible de monter boot_pool sur $BOOT"
        fi
    else
        ok "boot_pool → $BOOT"
    fi
    export BOOT

    # Créer le répertoire des symlinks ZBM ($BOOT/boot/)
    mkdir -p "$BOOT/boot"

    _mount_images_dataset
}

_mount_images_dataset() {
    # boot_pool/images : dataset enfant, monté sur $BOOT/images
    # Indispensable pour trouver les kernels, rootfs, modules.
    if ! zfs list boot_pool/images >/dev/null 2>&1; then
        warn "boot_pool/images absent — création via étape 2 (datasets-check.sh)"
        return 0
    fi
    if mountpoint -q "$BOOT/images" 2>/dev/null; then
        ok "boot_pool/images déjà monté → $BOOT/images"
        return 0
    fi
    mkdir -p "$BOOT/images"
    if zfs mount boot_pool/images 2>/dev/null; then
        ok "boot_pool/images → $BOOT/images"
    else
        # Fallback
        mount -t zfs boot_pool/images "$BOOT/images" 2>/dev/null             && ok "boot_pool/images → $BOOT/images (mount -t zfs)"             || warn "boot_pool/images : montage échoué (non bloquant)"
    fi
}

locate_boot() {
    # Vérifie que BOOT est valide ; monte si nécessaire.
    # Appelé avant chaque étape pour garantir que $BOOT est toujours disponible.
    if [[ -n "${BOOT:-}" ]] && mountpoint -q "$BOOT" 2>/dev/null; then
        # boot_pool/images peut avoir été démonté — vérifier
        mountpoint -q "$BOOT/images" 2>/dev/null || _mount_images_dataset
        return 0
    fi
    mount_boot_pool
}

_cleanup_boot_deploy() {
    # Démonter dans l'ordre : enfant avant parent
    mountpoint -q "${BOOT:-}/images" 2>/dev/null         && { zfs unmount boot_pool/images 2>/dev/null || umount "$BOOT/images" 2>/dev/null; } || true
    zbm_cleanup_boot 2>/dev/null || true
}
trap _cleanup_boot_deploy EXIT

# =============================================================================
# EXÉCUTION D'UNE ÉTAPE
# =============================================================================
run_step() {
    local script="$LIB/$1" label="$2"
    step "$label"
    [[ -f "$script" ]] || err "Script manquant : $script"
    [[ -f "$CONFIG_FILE" ]] && source "$CONFIG_FILE"
    # S'assurer que BOOT est localisé et exporté avant chaque étape
    locate_boot
    bash "$script" || err "Échec : $label"
    ok "$label terminé"
    echo ""
    read -rp "  Appuyez sur Entrée pour continuer..."
}

# =============================================================================
# MENU PRINCIPAL
# =============================================================================
main_menu() {
    while true; do
        clear
        echo -e "${CYAN}${BOLD}"
        echo "╔══════════════════════════════════════════════════════════════╗"
        echo "║   ZBM DEPLOY — Debian live trixie                           ║"
        echo "║   i5-11400 / Z490 UD / 2×NVMe + 5×SATA                    ║"
        echo "║                                                              ║"
        echo "║   Prérequis : partitionner et créer les pools manuellement  ║"
        echo "╚══════════════════════════════════════════════════════════════╝"
        echo -e "${NC}"

        if [[ -f "$CONFIG_FILE" ]]; then
            source "$CONFIG_FILE"
            echo -e "  ${GREEN}Config${NC} : $CONFIG_FILE"
            echo "    NVMe-A=${NVME_A:-?}  EFI=${EFI_PART:-?}  Kernel=${KERNEL_VER:-?}  Label=${ROOTFS_LABEL:-?}"
            BOOT_DISPLAY=$(zfs mount 2>/dev/null | awk '$1=="boot_pool"{print $2}' || true)
            IMAGES_DISPLAY=$(zfs mount 2>/dev/null | awk '$1=="boot_pool/images"{print $2}' || true)
            echo "    boot_pool : ${BOOT_DISPLAY:-non monté}  (BOOT=${BOOT:-non défini})"
            echo "    images    : ${IMAGES_DISPLAY:-(non monté)}  ← kernels/rootfs/modules ici"
            [[ -n "${STREAM_KEY:-}" ]] && echo "    Stream : configuré" || echo "    Stream : —"
        else
            echo -e "  ${YELLOW}Config non détectée — lancez l'étape 1 (Détecter)${NC}"
        fi

        echo ""
        echo "  ─── ÉTAPES ──────────────────────────────────────────────────"
        echo "  1)  Détecter l'environnement (NVMe, EFI, pools, datasets)"
        echo "  2)  Vérifier / créer les datasets manquants"
        echo "  3)  Installer le rootfs.sfs"
        echo "  4)  Construire python-3.11.sfs"
        echo "  5)  Construire l'initramfs"
        echo "  6)  Installer ZFSBootMenu"
        echo "  7)  Générer les presets"
        echo "  8)  Installer le failsafe"
        echo ""
        echo "  ─── UTILITAIRES ─────────────────────────────────────────────"
        echo "  10) Installer les paquets Debian nécessaires"
        echo "  11) Configuration complémentaire (label/kernel/stream)"
        echo "  12) Statut pools ZFS"
        echo "  13) Lister les rootfs .sfs disponibles"
        echo ""
        echo "  ─── DÉPLOIEMENT COMPLET ─────────────────────────────────────"
        echo "  9)  Tout déployer (étapes 1→8)"
        echo ""
        echo "  0)  Quitter"
        echo ""
        echo -n "  Choix : "
        read -r CHOICE

        case "$CHOICE" in
            9)
                step "Montage boot_pool + boot_pool/images"
                mount_boot_pool
                [[ ! -f "$CONFIG_FILE" ]] && { run_step detect.sh "Détection"; source "$CONFIG_FILE"; }
                install_packages
                run_step datasets-check.sh  "Vérification datasets"
                configure_extra
                run_step rootfs.sh          "Installation rootfs"
                run_step python-sfs.sh      "Construction python.sfs"
                run_step initramfs.sh       "Construction initramfs"
                run_step zbm.sh             "Installation ZFSBootMenu"
                run_step presets.sh         "Génération presets"
                run_step failsafe.sh        "Installation failsafe"
                echo ""
                echo -e "${GREEN}${BOLD}✅ Déploiement terminé — retirez le support live et redémarrez${NC}"
                read -rp "  Entrée..."
                ;;
            1)  mount_boot_pool; run_step detect.sh "Détection" ;;
            2)  run_step datasets-check.sh  "Vérification datasets" ;;
            3)  run_step rootfs.sh          "Installation rootfs" ;;
            4)  run_step python-sfs.sh      "Construction python.sfs" ;;
            5)  run_step initramfs.sh       "Construction initramfs" ;;
            6)  run_step zbm.sh             "Installation ZFSBootMenu" ;;
            7)  run_step presets.sh         "Génération presets" ;;
            8)  run_step failsafe.sh        "Installation failsafe" ;;
            10) install_packages ;;
            11) configure_extra ;;
            12) zpool list; echo ""; zfs list | head -40; read -rp "  Entrée..." ;;
            14) step "Montage boot_pool + boot_pool/images"; mount_boot_pool ;;
            13)
                echo ""
                find "${ZBM_BOOT:-/mnt/zbm/boot}" /mnt /run/live/medium -name "*.sfs" 2>/dev/null | while read -r f; do
                    echo "  $(du -sh "$f" | cut -f1)  $f"
                done
                read -rp "  Entrée..."
                ;;
            0) exit 0 ;;
            *) echo "  Choix invalide" ;;
        esac
    done
}

main_menu
