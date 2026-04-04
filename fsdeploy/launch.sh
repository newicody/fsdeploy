#!/usr/bin/env bash
# =============================================================================
# launch.sh — Bootstrap fsdeploy
#
# Fonctionne sur :
#   • Debian Live Trixie (comportement historique)
#   • Debian Trixie installé (APT prudent, pas d'écrasement)
#   • Toute Debian trixie existante
#
# S'exécute en UTILISATEUR NORMAL — sudo uniquement pour les opérations
# qui l'exigent (apt, groupadd, chown, sudoers, dkms…).
#
# Usage :
#   bash launch.sh                          # premier bootstrap
#   bash launch.sh --update                 # git pull + pip + migration config
#   bash launch.sh --dev                    # dépôt local, pas de clone
#   bash launch.sh --repo URL --branch X    # dépôt alternatif
#   bash launch.sh --user alice             # forcer l'utilisateur cible
# =============================================================================
set -euo pipefail
IFS=$'\n\t'

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────────────────────────
REPO_URL="${FSDEPLOY_REPO:-https://github.com/newicody/fsdeploy.git}"
REPO_BRANCH="${FSDEPLOY_BRANCH:-main}"
INSTALL_DIR="/opt/fsdeploy"
VENV_DIR="${INSTALL_DIR}/.venv"
LOG_DIR="${INSTALL_DIR}/logs"
ENV_FILE="${INSTALL_DIR}/.env"
FSDEPLOY_GROUP="fsdeploy"
SUDOERS_FILE="/etc/sudoers.d/10-fsdeploy"
WRAPPER="/usr/local/bin/fsdeploy"
SERVE_WRAPPER="/usr/local/bin/fsdeploy-web"
DKMS_WAIT_MAX=180   # secondes max pour la compilation DKMS
DEV_MODE=0
UPDATE_MODE=0
FORCED_USER=""

# ─────────────────────────────────────────────────────────────────────────────
# COULEURS
# ─────────────────────────────────────────────────────────────────────────────
if [[ -t 1 ]]; then
    CR="\033[0m" CB="\033[1m" CG="\033[32m" CY="\033[33m" CE="\033[31m" CC="\033[36m"
else
    CR="" CB="" CG="" CY="" CE="" CC=""
fi

step()  { printf "\n${CB}▶  %s${CR}\n"    "$*"; }
ok()    { printf "${CG}   ✅  %s${CR}\n"  "$*"; }
info()  { printf "${CC}   →   %s${CR}\n"  "$*"; }
warn()  { printf "${CY}   ⚠   %s${CR}\n"  "$*"; }
err()   { printf "${CE}   ❌  %s${CR}\n"  "$*" >&2; }
die()   { err "$*"; exit 1; }
srun()  { info "sudo $*"; sudo "$@"; }

# ─────────────────────────────────────────────────────────────────────────────
# PARSE ARGUMENTS
# ─────────────────────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case $1 in
        --repo)    REPO_URL="$2";    shift 2 ;;
        --branch)  REPO_BRANCH="$2"; shift 2 ;;
        --dev)     DEV_MODE=1;       shift   ;;
        --update)  UPDATE_MODE=1;    shift   ;;
        --user)    FORCED_USER="$2"; shift 2 ;;
        -h|--help)
            printf "Usage: bash launch.sh [--repo URL] [--branch NAME] [--dev] [--update] [--user NOM]\n"
            exit 0 ;;
        *) warn "Argument ignoré : $1"; shift ;;
    esac
done

# ─────────────────────────────────────────────────────────────────────────────
# RÉSOLUTION DE L'UTILISATEUR RÉEL
# Priorité : --user > SUDO_USER > USER courant > interactif
# ─────────────────────────────────────────────────────────────────────────────
_resolve_user() {
    local u=""
    if   [[ -n "${FORCED_USER:-}" ]];                              then u="$FORCED_USER"
    elif [[ -n "${SUDO_USER:-}" && "$SUDO_USER" != "root" ]];      then u="$SUDO_USER"
    elif [[ "$(id -u)" -ne 0 ]];                                   then u="${USER:-$(id -un)}"
    else
        printf "${CY}Lancé en root sans SUDO_USER — quel utilisateur possédera fsdeploy ?${CR}\n"
        while true; do
            read -rp "  Utilisateur : " u
            [[ -z "$u" ]] && { warn "Nom vide."; continue; }
            id "$u" &>/dev/null && break
            err "Utilisateur '$u' introuvable."
        done
    fi
    id "$u" &>/dev/null || die "Utilisateur '$u' introuvable dans /etc/passwd."
    printf '%s' "$u"
}

REAL_USER="$(_resolve_user)"
REAL_HOME="$(getent passwd "$REAL_USER" | cut -d: -f6)"
REAL_UID="$(id -u  "$REAL_USER")"
REAL_GID="$(id -g  "$REAL_USER")"

# ─────────────────────────────────────────────────────────────────────────────
# EXÉCUTION EN TANT QUE REAL_USER (git, python, pip — jamais root)
# ─────────────────────────────────────────────────────────────────────────────
as_user() {
    info "[${REAL_USER}] $*"
    if [[ "$(id -un)" == "$REAL_USER" ]]; then
        "$@"
    else
        sudo -u "$REAL_USER" "$@"
    fi
}

# ─────────────────────────────────────────────────────────────────────────────
# DÉTECTION : LIVE vs INSTALLÉ
# ─────────────────────────────────────────────────────────────────────────────
_is_live() {
    grep -qiE 'boot=live|live-media|casper|nopersistent' /proc/cmdline 2>/dev/null && return 0
    [[ -d /run/live ]]         && return 0
    [[ -f /etc/live/config ]]  && return 0
    local entries
    entries=$(grep -cvE '^\s*#|^\s*$' /etc/fstab 2>/dev/null || true)
    [[ "${entries:-0}" -lt 3 ]] && return 0
    return 1
}

IS_LIVE=0
_is_live && IS_LIVE=1

# ─────────────────────────────────────────────────────────────────────────────
# VÉRIFICATIONS PRÉ-BOOTSTRAP
# ─────────────────────────────────────────────────────────────────────────────
_pre_checks() {
    [[ "$(uname -m)" == "x86_64" ]] \
        || die "Architecture non supportée : $(uname -m) (amd64 requis)"

    local codename=""
    codename=$(. /etc/os-release 2>/dev/null && printf '%s' "${VERSION_CODENAME:-}") || true
    [[ "$codename" == "trixie" ]] \
        || warn "Codename Debian détecté : '${codename}' — trixie attendu. Continuer peut casser APT."

    local avail_mb
    avail_mb=$(df --output=avail -m "${INSTALL_DIR%/*}" 2>/dev/null | tail -1 | tr -d ' ') || avail_mb=9999
    [[ "${avail_mb:-0}" -ge 512 ]] \
        || die "Espace insuffisant sur ${INSTALL_DIR%/*} : ${avail_mb} MB disponibles (512 MB requis)"

    command -v sudo &>/dev/null \
        || die "sudo introuvable — installez-le : su -c 'apt-get install sudo'"
    if [[ "$(id -u)" -ne 0 ]]; then
        sudo -v 2>/dev/null \
            || die "Droits sudo insuffisants pour '$(id -un)'. Lancez via : sudo bash launch.sh"
    fi
}

# ─────────────────────────────────────────────────────────────────────────────
# BANNIÈRE
# ─────────────────────────────────────────────────────────────────────────────
printf "\n${CB}"
printf "╔══════════════════════════════════════════════════════════╗\n"
printf "║         fsdeploy — bootstrap Debian Trixie               ║\n"
printf "╚══════════════════════════════════════════════════════════╝\n"
printf "${CR}\n"
info "Utilisateur cible  : ${CB}${REAL_USER}${CR}  (uid=${REAL_UID} gid=${REAL_GID})"
info "Répertoire install : ${INSTALL_DIR}"
info "Dépôt              : ${REPO_URL}  [${REPO_BRANCH}]"
info "Environnement      : $( [[ $IS_LIVE -eq 1 ]] && printf 'Debian Live' || printf 'Debian installé' )"
[[ $DEV_MODE    -eq 1 ]] && info "${CY}Mode dev activé${CR}"
[[ $UPDATE_MODE -eq 1 ]] && info "${CY}Mode update activé${CR}"
printf "\n"

_pre_checks

# ═══════════════════════════════════════════════════════════════════════════════
# MODE UPDATE — git pull + pip + migration config uniquement
# ═══════════════════════════════════════════════════════════════════════════════
if [[ $UPDATE_MODE -eq 1 ]]; then
    step "MODE UPDATE"

    # 1. git pull
    if [[ -d "${INSTALL_DIR}/.git" ]]; then
        as_user git -C "$INSTALL_DIR" pull --quiet origin "$REPO_BRANCH"
        ok "Dépôt mis à jour"
    else
        warn "Dépôt absent dans ${INSTALL_DIR} — clone nécessaire. Relancer sans --update."
        exit 1
    fi

    # 2. pip install -r requirements.txt
    if [[ -f "${INSTALL_DIR}/requirements.txt" ]] && [[ -x "${VENV_DIR}/bin/pip" ]]; then
        as_user "$VENV_DIR/bin/pip" install --quiet --upgrade -r "${INSTALL_DIR}/requirements.txt"
        ok "Dépendances Python mises à jour"
    fi

    # 3. Migration config
    if [[ -x "${VENV_DIR}/bin/python3" ]]; then
        as_user "$VENV_DIR/bin/python3" - << 'PYEOF'
import sys, os
sys.path.insert(0, os.environ.get("FSDEPLOY_INSTALL_DIR", "/opt/fsdeploy"))
try:
    from fsdeploy.config import FsDeployConfig
    cfg = FsDeployConfig.default(create=False)
    cfg._apply_defaults()
    cfg.save()
    print("   →   Config migrée (nouvelles clés ajoutées, valeurs existantes conservées)")
except FileNotFoundError:
    print("   →   Pas de config existante — ignoré")
except Exception as e:
    print(f"   ⚠   Migration config ignorée : {e}")
PYEOF
    fi

    # 4. Mettre à jour .env
    as_user bash -c "cat > '${ENV_FILE}'" << ENVEOF
# fsdeploy — variables d'environnement
# Généré par launch.sh — $(date '+%Y-%m-%d %H:%M:%S')
FSDEPLOY_USER="${REAL_USER}"
FSDEPLOY_GROUP="${FSDEPLOY_GROUP}"
FSDEPLOY_INSTALL_DIR="${INSTALL_DIR}"
FSDEPLOY_VENV="${VENV_DIR}"
FSDEPLOY_LOG_DIR="${LOG_DIR}"
ENVEOF
    srun chmod 640 "$ENV_FILE"
    srun chown "${REAL_USER}:${FSDEPLOY_GROUP}" "$ENV_FILE"
    ok ".env mis à jour"

    printf "\n${CG}${CB}   ✅  Update terminé${CR}\n\n"

    # Lancer directement
    if [[ "$(id -un)" == "$REAL_USER" ]]; then
        exec "$VENV_DIR/bin/python3" -m fsdeploy "$@"
    else
        exec sudo -u "$REAL_USER" -g "$FSDEPLOY_GROUP" \
             "$VENV_DIR/bin/python3" -m fsdeploy "$@"
    fi
fi

# ═══════════════════════════════════════════════════════════════════════════════
# BOOTSTRAP COMPLET (premier lancement ou --dev)
# ═══════════════════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────────────────────
# 1. SOURCES APT
# Comportement adapté : Live → écriture directe / Installé → ajout prudent
# ─────────────────────────────────────────────────────────────────────────────
step "1/9 — Sources APT"

if [[ $IS_LIVE -eq 1 ]]; then
    sudo tee /etc/apt/sources.list > /dev/null << 'EOF'
deb http://deb.debian.org/debian trixie main contrib non-free non-free-firmware
deb-src http://deb.debian.org/debian trixie main contrib non-free non-free-firmware

deb http://deb.debian.org/debian trixie-backports main contrib non-free non-free-firmware
EOF
    info "sources.list remplacé (live)"
else
    local_sources=/etc/apt/sources.list

    if ! grep -q "trixie main contrib non-free" "$local_sources" 2>/dev/null; then
        if grep -q "trixie" "$local_sources" 2>/dev/null; then
            srun sed -i \
                's|^\(deb .*trixie main\)\s*$|\1 contrib non-free non-free-firmware|' \
                "$local_sources"
            info "contrib/non-free ajouté à la ligne trixie existante"
        else
            sudo tee -a "$local_sources" > /dev/null << 'EOF'

# Ajouté par fsdeploy/launch.sh
deb http://deb.debian.org/debian trixie main contrib non-free non-free-firmware
EOF
            info "Entrée trixie ajoutée"
        fi
    else
        info "contrib/non-free déjà présent dans sources.list"
    fi

    local bp_file=/etc/apt/sources.list.d/trixie-backports.list
    if ! grep -qR "trixie-backports" /etc/apt/sources.list /etc/apt/sources.list.d/ 2>/dev/null; then
        sudo tee "$bp_file" > /dev/null << 'EOF'
deb http://deb.debian.org/debian trixie-backports main contrib non-free non-free-firmware
EOF
        info "Backports ajoutés dans ${bp_file}"
    else
        info "Backports déjà configurés"
    fi
fi

sudo mkdir -p /etc/apt/preferences.d
sudo tee /etc/apt/preferences.d/backports.pref > /dev/null << 'EOF'
Package: *
Pin: release a=trixie-backports
Pin-Priority: 100
EOF

srun apt-get update -qq
ok "Sources APT configurées"

# ─────────────────────────────────────────────────────────────────────────────
# 2. PAQUETS SYSTÈME
# ─────────────────────────────────────────────────────────────────────────────
step "2/9 — Paquets système"

srun env DEBIAN_FRONTEND=noninteractive \
    apt-get install -y --no-install-recommends \
        linux-headers-$(uname -r) \
        zfsutils-linux \
        zfs-dkms \
        squashfs-tools \
        zstd xz-utils lz4 \
        dracut dracut-core \
        efibootmgr \
        dosfstools gdisk parted \
        git \
        python3 python3-pip python3-venv python3-dev \
        build-essential \
        ffmpeg \
        wget curl rsync \
        pv \
        sudo \
        acl \
        dkms

ok "Paquets installés"

# ─────────────────────────────────────────────────────────────────────────────
# 3. ATTENTE COMPILATION DKMS ZFS
# ─────────────────────────────────────────────────────────────────────────────
step "3/9 — Compilation DKMS zfs"

_wait_dkms() {
    local elapsed=0
    local kver
    kver=$(uname -r)

    if modinfo zfs &>/dev/null; then
        ok "Module ZFS déjà présent dans le noyau"
        return 0
    fi

    info "Attente de la compilation DKMS zfs (max ${DKMS_WAIT_MAX}s)..."
    while true; do
        local status
        status=$(dkms status zfs 2>/dev/null || true)

        if echo "$status" | grep -q "installed"; then
            printf "\n"
            ok "DKMS zfs compilé et installé"
            return 0
        fi

        if [[ $elapsed -ge $DKMS_WAIT_MAX ]]; then
            printf "\n"
            warn "Timeout DKMS (${DKMS_WAIT_MAX}s) — le module ZFS peut nécessiter un reboot"
            return 1
        fi

        printf "."
        sleep 5
        elapsed=$(( elapsed + 5 ))
    done
}

_wait_dkms || true

if ! lsmod 2>/dev/null | grep -q '^zfs'; then
    sudo modprobe zfs 2>/dev/null \
        && ok "Module ZFS chargé" \
        || warn "Impossible de charger ZFS maintenant — reboot peut être nécessaire"
else
    ok "Module ZFS déjà chargé"
fi

# ─────────────────────────────────────────────────────────────────────────────
# 4. GROUPE fsdeploy + APPARTENANCE UTILISATEUR
# ─────────────────────────────────────────────────────────────────────────────
step "4/9 — Groupe '${FSDEPLOY_GROUP}' et appartenances"

if ! getent group "$FSDEPLOY_GROUP" &>/dev/null; then
    srun groupadd --system "$FSDEPLOY_GROUP"
    info "Groupe '${FSDEPLOY_GROUP}' créé"
else
    info "Groupe '${FSDEPLOY_GROUP}' déjà présent"
fi

NEEDED_GROUPS=("$FSDEPLOY_GROUP" "disk")
getent group sudo  &>/dev/null && NEEDED_GROUPS+=("sudo")
getent group video &>/dev/null && NEEDED_GROUPS+=("video")

GROUPS_ADDED=()
for grp in "${NEEDED_GROUPS[@]}"; do
    if getent group "$grp" &>/dev/null; then
        if ! id -nG "$REAL_USER" | tr ' ' '\n' | grep -qx "$grp"; then
            srun usermod -aG "$grp" "$REAL_USER"
            GROUPS_ADDED+=("$grp")
            info "${REAL_USER} → groupe '${grp}' ajouté"
        else
            info "${REAL_USER} déjà dans '${grp}'"
        fi
    fi
done

ok "Groupes : ${NEEDED_GROUPS[*]}"

# ─────────────────────────────────────────────────────────────────────────────
# 5. RÉPERTOIRE D'INSTALLATION — permissions + ACL POSIX
# ─────────────────────────────────────────────────────────────────────────────
step "5/9 — Répertoire ${INSTALL_DIR}"

srun mkdir -p "$INSTALL_DIR" "$LOG_DIR"
srun chown -R "${REAL_USER}:${FSDEPLOY_GROUP}" "$INSTALL_DIR"
srun chmod -R 2775 "$INSTALL_DIR"

if command -v setfacl &>/dev/null; then
    srun setfacl -Rdm "u::rwX,g::rwX,o::rX"    "$INSTALL_DIR"
    srun setfacl -Rm  "g:${FSDEPLOY_GROUP}:rwX" "$INSTALL_DIR"
    info "ACL POSIX appliquées"
fi

ok "${INSTALL_DIR} → ${REAL_USER}:${FSDEPLOY_GROUP}  chmod 2775"

# ─────────────────────────────────────────────────────────────────────────────
# 6. SUDOERS — groupe fsdeploy, NOPASSWD ciblé
# ─────────────────────────────────────────────────────────────────────────────
step "6/9 — Sudoers pour '${FSDEPLOY_GROUP}'"

_bin() {
    for p in "/usr/sbin/$1" "/sbin/$1" "/usr/bin/$1" "/bin/$1"; do
        [[ -x "$p" ]] && { printf '%s' "$p"; return; }
    done
    printf '/usr/sbin/%s' "$1"
}
_cmd() { command -v "$1" 2>/dev/null || printf '/usr/bin/%s' "$1"; }

B_ZPOOL="$(_bin zpool)"        B_ZFS="$(_bin zfs)"
B_DRACUT="$(_bin dracut)"      B_MODPROBE="$(_bin modprobe)"
B_RMMOD="$(_bin rmmod)"        B_INSMOD="$(_bin insmod)"
B_MOUNT="$(_cmd mount)"        B_UMOUNT="$(_cmd umount)"
B_MKSQUASHFS="$(_cmd mksquashfs)"
B_EFIBOOTMGR="$(_cmd efibootmgr)"
B_SGDISK="$(_bin sgdisk)"      B_PARTED="$(_bin parted)"
B_WIPEFS="$(_bin wipefs)"      B_DD="$(_cmd dd)"
B_TEE="$(_cmd tee)"            B_INSTALL_BIN="$(_cmd install)"
B_CHMOD="$(_cmd chmod)"        B_CHOWN="$(_cmd chown)"
B_APTGET="$(_cmd apt-get)"     B_DPKG="$(_cmd dpkg)"

SUDOERS_CONTENT="# fsdeploy — opérations privilégiées ZFS / boot / système
# Généré par launch.sh — $(date '+%Y-%m-%d %H:%M:%S')
# Groupe  : ${FSDEPLOY_GROUP}  |  Système : $(uname -r)

Defaults:%${FSDEPLOY_GROUP} !authenticate

# ── ZFS ───────────────────────────────────────────────────────────────────────
%${FSDEPLOY_GROUP} ALL=(ALL:ALL) NOPASSWD: ${B_ZPOOL}
%${FSDEPLOY_GROUP} ALL=(ALL:ALL) NOPASSWD: ${B_ZFS}

# ── Montage / démontage ───────────────────────────────────────────────────────
%${FSDEPLOY_GROUP} ALL=(ALL:ALL) NOPASSWD: ${B_MOUNT}
%${FSDEPLOY_GROUP} ALL=(ALL:ALL) NOPASSWD: ${B_UMOUNT}

# ── Initramfs ─────────────────────────────────────────────────────────────────
%${FSDEPLOY_GROUP} ALL=(ALL:ALL) NOPASSWD: ${B_DRACUT}

# ── Images squash ─────────────────────────────────────────────────────────────
%${FSDEPLOY_GROUP} ALL=(ALL:ALL) NOPASSWD: ${B_MKSQUASHFS}

# ── EFI / partitionnement ─────────────────────────────────────────────────────
%${FSDEPLOY_GROUP} ALL=(ALL:ALL) NOPASSWD: ${B_EFIBOOTMGR}
%${FSDEPLOY_GROUP} ALL=(ALL:ALL) NOPASSWD: ${B_SGDISK}
%${FSDEPLOY_GROUP} ALL=(ALL:ALL) NOPASSWD: ${B_PARTED}
%${FSDEPLOY_GROUP} ALL=(ALL:ALL) NOPASSWD: ${B_WIPEFS}

# ── Écriture bas niveau ───────────────────────────────────────────────────────
%${FSDEPLOY_GROUP} ALL=(ALL:ALL) NOPASSWD: ${B_DD}
%${FSDEPLOY_GROUP} ALL=(ALL:ALL) NOPASSWD: ${B_TEE}
%${FSDEPLOY_GROUP} ALL=(ALL:ALL) NOPASSWD: ${B_INSTALL_BIN}
%${FSDEPLOY_GROUP} ALL=(ALL:ALL) NOPASSWD: ${B_CHMOD}
%${FSDEPLOY_GROUP} ALL=(ALL:ALL) NOPASSWD: ${B_CHOWN}

# ── Modules noyau ─────────────────────────────────────────────────────────────
%${FSDEPLOY_GROUP} ALL=(ALL:ALL) NOPASSWD: ${B_MODPROBE}
%${FSDEPLOY_GROUP} ALL=(ALL:ALL) NOPASSWD: ${B_RMMOD}
%${FSDEPLOY_GROUP} ALL=(ALL:ALL) NOPASSWD: ${B_INSMOD}

# ── Paquets ───────────────────────────────────────────────────────────────────
%${FSDEPLOY_GROUP} ALL=(ALL:ALL) NOPASSWD: ${B_APTGET}
%${FSDEPLOY_GROUP} ALL=(ALL:ALL) NOPASSWD: ${B_DPKG}
"

SUDOERS_TMP="$(mktemp /tmp/fsdeploy-sudoers.XXXXXX)"
trap 'rm -f "$SUDOERS_TMP"' EXIT
printf '%s' "$SUDOERS_CONTENT" > "$SUDOERS_TMP"
chmod 440 "$SUDOERS_TMP"

if sudo visudo -cf "$SUDOERS_TMP" > /dev/null 2>&1; then
    srun cp    "$SUDOERS_TMP" "$SUDOERS_FILE"
    srun chmod 440 "$SUDOERS_FILE"
    ok "sudoers valide → ${SUDOERS_FILE}"
else
    rm -f "$SUDOERS_TMP"
    die "Syntaxe sudoers invalide — corrigez launch.sh"
fi

# ─────────────────────────────────────────────────────────────────────────────
# 7. DÉPÔT GIT
# ─────────────────────────────────────────────────────────────────────────────
step "7/9 — Dépôt Git"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"

# Cas 1 : Mode dev — utiliser le dossier courant
if [[ $DEV_MODE -eq 1 && -f "${SCRIPT_DIR}/fsdeploy/__init__.py" ]]; then
    INSTALL_DIR="$SCRIPT_DIR"
    info "Mode DEV — Utilisation du dossier courant : ${INSTALL_DIR}"
else
    # Cas 2 : Le dépôt existe déjà, on met à jour
    if [[ -d "${INSTALL_DIR}/.git" ]]; then
        as_user git -C "$INSTALL_DIR" fetch --quiet origin
        as_user git -C "$INSTALL_DIR" reset --hard "origin/${REPO_BRANCH}"
        ok "Dépôt mis à jour via reset --hard"

    # Cas 3 : Le dossier existe mais n'est pas un dépôt Git
    else
        info "Initialisation du dépôt dans un dossier existant..."
        as_user mkdir -p "$INSTALL_DIR"
        as_user git -C "$INSTALL_DIR" init --quiet
        as_user git -C "$INSTALL_DIR" remote add origin "$REPO_URL" 2>/dev/null || true
        as_user git -C "$INSTALL_DIR" fetch --quiet origin
        as_user git -C "$INSTALL_DIR" checkout -f "$REPO_BRANCH"
        as_user git -C "$INSTALL_DIR" branch --set-upstream-to="origin/${REPO_BRANCH}" "$REPO_BRANCH" 2>/dev/null || true
        ok "Dépôt initialisé et synchronisé dans ${INSTALL_DIR}"
    fi
fi

# Ré-appliquer les permissions après le clone/fetch
srun chown -R "${REAL_USER}:${FSDEPLOY_GROUP}" "$INSTALL_DIR"
srun chmod -R 2775 "$INSTALL_DIR"

# ─────────────────────────────────────────────────────────────────────────────
# 8. ENVIRONNEMENT VIRTUEL PYTHON
# ─────────────────────────────────────────────────────────────────────────────
step "8/9 — Environnement virtuel Python"

if [[ ! -d "$VENV_DIR" ]]; then
    as_user python3 -m venv --system-site-packages "$VENV_DIR"
    ok "Virtualenv créé → ${VENV_DIR}"
fi

as_user "$VENV_DIR/bin/pip" install --quiet --upgrade pip setuptools wheel

if [[ -f "${INSTALL_DIR}/requirements.txt" ]]; then
    as_user "$VENV_DIR/bin/pip" install --quiet -r "${INSTALL_DIR}/requirements.txt"
    ok "Dépendances Python installées"
else
    # Fallback : dépendances minimales directement
    as_user "$VENV_DIR/bin/pip" install --quiet \
        "textual>=8.2.1,<9" \
        "textual-dev>=1.8.0,<2" \
        "rich>=14.3.3,<15" \
        "configobj>=5.0.8" \
        "typer>=0.12.0" \
        "structlog>=24.0.0" \
        "psutil>=5.9.0" \
        "pyudev>=0.24.0" \
        "packaging>=23.0" \
        "humanize>=4.0.0" \
        "watchfiles>=0.21.0" \
        "python-ffmpeg>=2.0.0"
    ok "Dépendances Python installées (inline fallback)"
fi

# Vérification versions Textual / Rich
_textual_ver=$("$VENV_DIR/bin/python3" -c "import textual; print(textual.__version__)" 2>/dev/null || echo "MISSING")
if [[ "$_textual_ver" == "MISSING" ]]; then
    warn "Textual non installé correctement — vérifiez requirements.txt"
elif [[ "${_textual_ver%%.*}" -lt 8 ]]; then
    warn "Textual $_textual_ver installé — version 8.x attendue"
else
    ok "Textual $_textual_ver installé"
fi

_rich_ver=$("$VENV_DIR/bin/python3" -c "import rich; print(rich.__version__)" 2>/dev/null || echo "MISSING")
if [[ "$_rich_ver" != "MISSING" ]]; then
    ok "Rich $_rich_ver installé"
fi

# Permissions venv
srun chown -R "${REAL_USER}:${FSDEPLOY_GROUP}" "$VENV_DIR"
srun chmod -R g+rX "$VENV_DIR"

# Fichier .env
as_user bash -c "cat > '${ENV_FILE}'" << ENVEOF
# fsdeploy — variables d'environnement
# Généré par launch.sh — $(date '+%Y-%m-%d %H:%M:%S')
FSDEPLOY_USER="${REAL_USER}"
FSDEPLOY_GROUP="${FSDEPLOY_GROUP}"
FSDEPLOY_INSTALL_DIR="${INSTALL_DIR}"
FSDEPLOY_VENV="${VENV_DIR}"
FSDEPLOY_LOG_DIR="${LOG_DIR}"
FSDEPLOY_TEXTUAL_VERSION="${_textual_ver}"
FSDEPLOY_RICH_VERSION="${_rich_ver}"
ENVEOF
srun chmod 640 "$ENV_FILE"
srun chown "${REAL_USER}:${FSDEPLOY_GROUP}" "$ENV_FILE"
ok ".env écrit → ${ENV_FILE}"

# Wrapper CLI
sudo tee "$WRAPPER" > /dev/null << WRAPPER_EOF
#!/usr/bin/env bash
# Wrapper fsdeploy — généré par launch.sh (ne pas éditer)
[ -f "${ENV_FILE}" ] && . "${ENV_FILE}"
exec "${VENV_DIR}/bin/python3" -m fsdeploy "\$@"
WRAPPER_EOF
srun chmod 755 "$WRAPPER"
ok "'fsdeploy' disponible → ${WRAPPER}"

# Wrapper web (textual serve)
sudo tee "$SERVE_WRAPPER" > /dev/null << WEBEOF
#!/usr/bin/env bash
# fsdeploy web mode — généré par launch.sh
# Usage : fsdeploy-web [--port 8080]
[ -f "${ENV_FILE}" ] && . "${ENV_FILE}"
PORT="\${1:-8080}"
if [ "\$1" = "--port" ]; then PORT="\$2"; fi
exec "${VENV_DIR}/bin/textual" serve "python3 -m fsdeploy" --port "\$PORT"
WEBEOF
srun chmod 755 "$SERVE_WRAPPER"
ok "'fsdeploy-web' disponible → ${SERVE_WRAPPER}"

# ─────────────────────────────────────────────────────────────────────────────
# 9. VÉRIFICATIONS POST-INSTALL
# ─────────────────────────────────────────────────────────────────────────────
step "9/9 — Vérifications"

_ok=0; _total=4

if as_user "$VENV_DIR/bin/python3" -c \
    "import sys; assert sys.version_info >= (3,11)" 2>/dev/null; then
    _ver=$(as_user "$VENV_DIR/bin/python3" -c "import sys; print(sys.version.split()[0])")
    ok "Python ${_ver}"; (( _ok++ )) || true
else
    warn "Python < 3.11 dans le venv"
fi

if command -v zpool &>/dev/null; then
    ok "zfsutils-linux présent"; (( _ok++ )) || true
else
    warn "zpool introuvable"
fi

if lsmod 2>/dev/null | grep -q '^zfs'; then
    ok "Module ZFS actif"; (( _ok++ )) || true
else
    warn "Module ZFS non chargé"
fi

if sudo -l -U "$REAL_USER" 2>/dev/null | grep -q "NOPASSWD.*zpool"; then
    ok "Sudoers actif pour ${REAL_USER}"; (( _ok++ )) || true
else
    warn "Sudoers pas encore actif (actif à la prochaine connexion)"
fi

# ─────────────────────────────────────────────────────────────────────────────
# RÉSUMÉ FINAL ET LANCEMENT
# ─────────────────────────────────────────────────────────────────────────────
printf "\n${CB}"
printf "╔══════════════════════════════════════════════════════════╗\n"
printf "║         ✅  Bootstrap terminé (%d/%d vérifications)       ║\n" "$_ok" "$_total"
printf "╚══════════════════════════════════════════════════════════╝\n"
printf "${CR}\n"
info "Utilisateur    : ${CB}${REAL_USER}${CR}"
info "Groupe         : ${CB}${FSDEPLOY_GROUP}${CR}"
info "Répertoire     : ${INSTALL_DIR}"
info "Venv           : ${VENV_DIR}"
info "Commande       : fsdeploy"
info "Mode web       : fsdeploy-web [--port 8080]"
info "Variables env  : ${ENV_FILE}"
info "Sudoers        : ${SUDOERS_FILE}"
printf "\n"

if [[ ${#GROUPS_ADDED[@]} -gt 0 ]]; then
    printf "${CY}  ⚠  Nouveaux groupes : %s${CR}\n" "${GROUPS_ADDED[*]}"
    printf "     Actifs à la prochaine session. Pour démarrer maintenant :\n\n"
    printf "       ${CB}exec sudo -u ${REAL_USER} -g ${FSDEPLOY_GROUP} ${VENV_DIR}/bin/python3 -m fsdeploy${CR}\n\n"
    printf "     Ou reconnectez-vous puis lancez : ${CB}fsdeploy${CR}\n\n"
else
    printf "   Lancement de fsdeploy...\n\n"
    if [[ "$(id -un)" == "$REAL_USER" ]]; then
        exec "$VENV_DIR/bin/python3" -m fsdeploy "$@"
    else
        exec sudo -u "$REAL_USER" -g "$FSDEPLOY_GROUP" \
             "$VENV_DIR/bin/python3" -m fsdeploy "$@"
    fi
fi
