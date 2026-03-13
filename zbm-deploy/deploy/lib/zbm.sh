#!/bin/bash
# lib/07-zbm.sh — Installation et configuration de ZFSBootMenu
# lib/08-presets.sh — Génération des presets JSON initiaux
# lib/09-failsafe.sh — Installation du failsafe
# Sourcé depuis deploy.sh avec config.sh déjà chargé

set -euo pipefail

# naming.sh fournit zbm_locate_boot(), zbm_cleanup_boot() et les fonctions de nommage
# Sourcé par deploy.sh OU directement si lancé seul
if [[ -z "$(type -t zbm_locate_boot 2>/dev/null)" ]]; then
    _NM="$(dirname "$0")/naming.sh"
    [[ -f "$_NM" ]] && source "$_NM" \
        || { echo "ERREUR: naming.sh introuvable — lancer depuis deploy.sh"; exit 1; }
fi

GREEN='\033[1;32m'; YELLOW='\033[1;33m'; RED='\033[1;31m'; NC='\033[0m'
ok()   { echo -e "  ${GREEN}✅ $*${NC}"; }
warn() { echo -e "  ${YELLOW}⚠️  $*${NC}"; }
err()  { echo -e "  ${RED}❌ $*${NC}"; exit 1; }
info() { echo -e "  ${GREEN}   $*${NC}"; }

# Localisation de boot_pool — utilise zbm_locate_boot() de naming.sh
# Sur Debian live /boot est occupé → boot_pool monté sur ${ZBM_BOOT:-/mnt/zbm/boot}
_MOUNTED_BOOT=0  # rétrocompat
_cleanup_boot() { zbm_cleanup_boot; }
trap _cleanup_boot EXIT
zbm_locate_boot || err "boot_pool introuvable — vérifiez les pools ZFS"
info "boot_pool -> $BOOT"

# EFI_PART est défini dans config.sh par detect.sh — pas besoin de NVME_A ici
# La résolution de _EFI_DEVICE est faite dans la section "Montage EFI" ci-dessous
# NVME_A n'est plus utilisé pour le montage EFI (utilisation de EFI_PART directement)
: "${EFI_PART:=}"  # variable may be empty, resolved dynamically below
# EFI_MNT : point de montage INDÉPENDANT de boot_pool (pas dedans)
# On monte la partition vfat temporairement pour y copier le .EFI
EFI_MNT="/mnt/efi-deploy-$$"
# Sous-répertoire EFI où ZFSBootMenu est installé (relatif au point de montage EFI)
ZBM_EFI_SUBDIR="${EFI_MNT}/EFI/ZBM"


# =============================================================================
# 1. MONTER LA PARTITION EFI
# =============================================================================
echo "  Montage de la partition EFI..."
mkdir -p "$EFI_MNT"

# EFI_PART est défini dans config.sh par detect.sh
# Ne pas supposer ${NVME_A}p1 — la partition EFI peut être sur n'importe quel device
_EFI_DEVICE="${EFI_PART:-}"

# Si EFI_PART absent, chercher dynamiquement
if [[ -z "$_EFI_DEVICE" ]] || [[ ! -b "$_EFI_DEVICE" ]]; then
    warn "EFI_PART non défini — détection dynamique..."
    _EFI_DEVICE=$(lsblk -lnpo NAME,PARTTYPE 2>/dev/null         | awk 'tolower($2) == "c12a7328-f81f-11d2-ba4b-00a0c93ec93b" {print $1; exit}' || true)
    [[ -b "$_EFI_DEVICE" ]]         || err "Partition EFI introuvable — vérifiez config.sh (EFI_PART) ou relancez l'étape 1"
    warn "EFI_PART détecté dynamiquement : $_EFI_DEVICE (relancez l'étape 1 pour le persister)"
fi

mount "$_EFI_DEVICE" "$EFI_MNT" 2>/dev/null ||     mount -t vfat "$_EFI_DEVICE" "$EFI_MNT" ||     err "Impossible de monter la partition EFI $_EFI_DEVICE"

mkdir -p "$ZBM_EFI_SUBDIR"
ok "EFI montée : $_EFI_DEVICE → $EFI_MNT"

# =============================================================================
# 2. INSTALLER ZFSBOOTMENU
# =============================================================================
echo "  Installation de ZFSBootMenu..."

ZBM_RELEASE_URL="https://get.zfsbootmenu.org/efi"
ZBM_EFI_FILE="$ZBM_EFI_SUBDIR/vmlinuz.EFI"

if [[ -f "$ZBM_EFI_FILE" ]]; then
    warn "ZFSBootMenu déjà présent — mise à jour ignorée"
    warn "Pour forcer : rm $ZBM_EFI_FILE et relancer"
else
    echo -n "  Téléchargement de ZFSBootMenu EFI..."
    _DL_OK=0
    if command -v wget >/dev/null 2>&1; then
        wget -q --timeout=30 --tries=2 -O "$ZBM_EFI_FILE" "$ZBM_RELEASE_URL" 2>/dev/null && _DL_OK=1
    fi
    if [[ $_DL_OK -eq 0 ]] && command -v curl >/dev/null 2>&1; then
        curl -fsSL --connect-timeout 30 --max-time 120 -o "$ZBM_EFI_FILE" "$ZBM_RELEASE_URL" 2>/dev/null && _DL_OK=1
    fi
    if [[ $_DL_OK -eq 1 ]] && [[ -s "$ZBM_EFI_FILE" ]]; then
        echo " OK"
        ok "ZFSBootMenu EFI téléchargé : $(du -sh "$ZBM_EFI_FILE" | cut -f1)"
    else
        [[ -f "$ZBM_EFI_FILE" ]] && rm -f "$ZBM_EFI_FILE"
        warn "Téléchargement échoué — utilisation de generate-zbm si disponible"
        # Fallback : générer depuis le source
        if command -v generate-zbm >/dev/null 2>&1; then
            generate-zbm --config /etc/zfsbootmenu/config.yaml --output "$ZBM_EFI_FILE"
            ok "ZFSBootMenu généré localement"
        else
            err "Impossible d'installer ZFSBootMenu (pas de réseau ni de generate-zbm)"
        fi
    fi
fi

# =============================================================================
# 3. CONFIGURATION ZFSBOOTMENU
# =============================================================================
echo "  Configuration ZFSBootMenu..."
mkdir -p /etc/zfsbootmenu

# NB: ManageImages:false car nos images sont gérées par deploy.sh, pas generate-zbm
# BootMountPoint: /boot = chemin dans le système réel booté (pas le live)
cat > /etc/zfsbootmenu/config.yaml << YAMLEOF
Global:
  ManageImages: false
  BootMountPoint: /boot
  DracutConfDir: /etc/zfsbootmenu/dracut.conf.d

Components:
  Enabled: false

EFI:
  ImageDir: /boot/efi/EFI/ZBM
  Versions: 1
  Enabled: true
YAMLEOF

ok "config.yaml créé"

# =============================================================================
# 3b. PROPRIÉTÉS ZBM SUR boot_pool
# =============================================================================
# ZBM scanne les pools ZFS pour trouver des "boot environments" :
#   - Dataset avec mountpoint=/ OU
#   - Dataset désigné par la propriété bootfs= du pool
#   ZBM monte le BE et cherche vmlinuz dans <be_root>/boot/vmlinuz
#
# Notre setup : boot_pool a mountpoint=legacy (pas mountpoint=/boot)
#   → ZBM peut le monter à sa racine et trouver boot/vmlinuz + boot/initrd.img
#   → Les symlinks sont créés par presets.sh dans $BOOT/boot/
#
# cachefile : permet à ZBM de retrouver les pools sans scan exhaustif
echo "  Configuration des propriétés ZBM sur boot_pool..."

# 1. mountpoint=legacy : ZBM gère le montage lui-même (pas zfs mount -a)
#    NB : nos scripts deploy utilisent mount -t zfs boot_pool <chemin> explicitement
if zfs get -H -o value mountpoint boot_pool 2>/dev/null | grep -qv 'legacy'; then
    zfs set mountpoint=legacy boot_pool         && ok "boot_pool mountpoint=legacy"         || warn "Impossible de changer mountpoint (pool peut-être importé read-only ?)"
else
    ok "boot_pool mountpoint=legacy (déjà configuré)"
fi

# 2. bootfs : indique à ZBM quel dataset utiliser comme boot environment
zpool set bootfs=boot_pool boot_pool     && ok "boot_pool bootfs=boot_pool"     || warn "zpool set bootfs échoué"

# 3. commandline ZBM sur le boot environment
#    ZBM passe ces paramètres au kernel lors du kexec
#    zbm_system=initial → notre initramfs-init démarre en mode init-only
zfs set org.zfsbootmenu:commandline="ro quiet loglevel=3 zbm_system=initial zbm_rootfs=none" boot_pool     && ok "org.zfsbootmenu:commandline configuré"     || warn "zfs set commandline échoué"

# 4. cachefile : accélère l'import au démarrage ZBM
zpool set cachefile=/etc/zfs/zpool.cache boot_pool 2>/dev/null || true
zpool set cachefile=/etc/zfs/zpool.cache fast_pool 2>/dev/null || true
zpool set cachefile=/etc/zfs/zpool.cache data_pool 2>/dev/null || true
ok "cachefile=/etc/zfs/zpool.cache"

# 5. Créer boot/ dans boot_pool pour que ZBM trouve les kernels
#    Les symlinks réels sont gérés par presets.sh → étape 7
#    Ici on crée juste le répertoire vide si absent
mkdir -p "$BOOT/boot"
info "boot_pool/boot/ prêt pour les symlinks kernel (étape 7)"

# =============================================================================
# 4. ENTRÉE UEFI VIA efibootmgr
# =============================================================================
echo "  Création de l'entrée UEFI..."

# Numéro de partition EFI
# Dériver disk + numéro de partition depuis _EFI_DEVICE (déjà résolu ci-dessus)
# efibootmgr a besoin de --disk (disque parent) et --part (numéro partition)
_EFI_DISK=$(lsblk -npo PKNAME "$_EFI_DEVICE" 2>/dev/null | head -1 | xargs || true)
if [[ -z "$_EFI_DISK" ]] || [[ ! -b "$_EFI_DISK" ]]; then
    # Fallback séquentiel : pN d'abord (NVMe), puis digits (SATA)
    # NE PAS chainer les deux sed : nvme0n1p1 → nvme0n1 → nvme0n  ← FAUX
    _stripped=$(echo "$_EFI_DEVICE" | sed 's/p[0-9]\+$//')
    if [[ "$_stripped" != "$_EFI_DEVICE" ]]; then
        _EFI_DISK="$_stripped"                               # NVMe : pN retiré
    else
        _EFI_DISK=$(echo "$_EFI_DEVICE" | sed 's/[0-9]\+$//') # SATA : digits
    fi
fi
[[ -b "$_EFI_DISK" ]] || err "Disque parent de $_EFI_DEVICE introuvable"

# Numéro de partition : lsblk est plus fiable que sed
EFI_PART_NUM=$(lsblk -npo PARTN "$_EFI_DEVICE" 2>/dev/null | head -1 | xargs || true)
if [[ -z "$EFI_PART_NUM" ]] || [[ ! "$EFI_PART_NUM" =~ ^[0-9]+$ ]]; then
    # Fallback : extraire depuis le nom
    EFI_PART_NUM="${_EFI_DEVICE##*[a-zA-Z]}"
    EFI_PART_NUM="${EFI_PART_NUM##*p}"
    [[ "$EFI_PART_NUM" =~ ^[0-9]+$ ]] || EFI_PART_NUM="1"
fi
info "EFI : disk=$_EFI_DISK  part=$EFI_PART_NUM  device=$_EFI_DEVICE"

if command -v efibootmgr >/dev/null 2>&1; then
    # Supprimer les entrées ZBM existantes (|| true : pas fatal si aucune)
    while read -r BOOT_NUM; do
        [[ -n "$BOOT_NUM" ]] || continue
        efibootmgr --delete-bootnum --bootnum "$BOOT_NUM" 2>/dev/null || true
        info "Entrée existante supprimée : Boot${BOOT_NUM}"
    done < <(efibootmgr 2>/dev/null \
        | grep -i "ZFSBootMenu" \
        | grep -oE 'Boot[0-9A-Fa-f]+' \
        | grep -oE '[0-9A-Fa-f]+' \
        || true)

    # ZBM EFI standalone :
    #   --loader '\EFI\ZBM\vmlinuz.EFI' : backslashes SIMPLES (séparateur UEFI)
    #            single-quotes bash → backslash littéral transmis à efibootmgr
    #   --unicode : cmdline passée au binaire EFI
    #              Invariant #23 : 'zbm.timeout=5 loglevel=4' via --unicode
    _EFI_RESULT=0
    efibootmgr \
        --create \
        --disk  "${_EFI_DISK}" \
        --part  "${EFI_PART_NUM}" \
        --label "ZFSBootMenu" \
        --loader '\EFI\ZBM\vmlinuz.EFI' \
        --unicode 'zbm.prefer=boot_pool zbm.timeout=5 loglevel=4' \
        2>&1 | sed 's/^/    /' || _EFI_RESULT=$?

    if [[ $_EFI_RESULT -ne 0 ]]; then
        err "efibootmgr a échoué (code ${_EFI_RESULT}) — vérifiez que le système est démarré en mode UEFI"
    fi

    ok "Entrée UEFI créée : ZFSBootMenu"
    efibootmgr 2>/dev/null | grep -i zbm | sed 's/^/    /'

    # Entrée de secours si backup présent
    ZBM_BACKUP="$ZBM_EFI_SUBDIR/vmlinuz-backup.EFI"
    if [[ -f "$ZBM_BACKUP" ]]; then
        efibootmgr \
            --create \
            --disk  "${_EFI_DISK}" \
            --part  "${EFI_PART_NUM}" \
            --label "ZFSBootMenu (Backup)" \
            --loader '\EFI\ZBM\vmlinuz-backup.EFI' \
            --unicode 'zbm.prefer=boot_pool zbm.timeout=5 loglevel=4' \
            2>/dev/null || true
        ok "Entrée UEFI backup créée"
    fi
else
    warn "efibootmgr non disponible — entrée UEFI à créer manuellement :"
    echo "    efibootmgr --create --disk ${_EFI_DISK} --part ${EFI_PART_NUM} \\"
    echo "               --label 'ZFSBootMenu' \\"
    echo "               --loader '\\EFI\\ZBM\\vmlinuz.EFI' \\"
    echo "               --unicode 'zbm.prefer=boot_pool zbm.timeout=5 loglevel=4'"
fi
