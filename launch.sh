#!/usr/bin/env bash
# =============================================================================
# launch.sh — Bootstrap fsdeploy depuis Debian Live Trixie
#
# Ce script fait UNE SEULE CHOSE : préparer l'environnement et lancer Python.
# Toute la logique métier est dans le code Python.
#
# Usage : bash launch.sh [--repo URL] [--branch NAME] [--dev]
# =============================================================================
set -euo pipefail

REPO_URL="${FSDEPLOY_REPO:-https://github.com/fsdeploy/fsdeploy.git}"
REPO_BRANCH="${FSDEPLOY_BRANCH:-main}"
INSTALL_DIR="/opt/fsdeploy"
VENV_DIR="$INSTALL_DIR/.venv"
DEV_MODE=0

# ── Parse args ──────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case $1 in
        --repo)    REPO_URL="$2";    shift 2 ;;
        --branch)  REPO_BRANCH="$2"; shift 2 ;;
        --dev)     DEV_MODE=1;       shift   ;;
        *)         shift ;;
    esac
done

# ── Root check ───────────────────────────────────────────────────────────────
[[ $EUID -eq 0 ]] || { echo "❌  Root requis : sudo bash launch.sh"; exit 1; }

echo "╔══════════════════════════════════════════════════════╗"
echo "║          fsdeploy — bootstrap Debian Live            ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# ── 1. Sources APT ────────────────────────────────────────────────────────────
echo "▶ Configuration APT (trixie contrib non-free + backports)..."
cat > /etc/apt/sources.list << 'EOF'
deb http://deb.debian.org/debian trixie main contrib non-free non-free-firmware
deb-src http://deb.debian.org/debian trixie main contrib non-free non-free-firmware

deb http://deb.debian.org/debian trixie-backports main contrib non-free non-free-firmware
EOF

# Préférences backports (priorité basse sauf si explicitement demandé)
cat > /etc/apt/preferences.d/backports.pref << 'EOF'
Package: *
Pin: release a=trixie-backports
Pin-Priority: 100
EOF

apt-get update -qq
echo "  ✅ Sources configurées"

# ── 2. Paquets système ────────────────────────────────────────────────────────
echo "▶ Installation des paquets..."
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    linux-headers-amd64 \
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
    2>/dev/null

echo "  ✅ Paquets installés"

# ── 3. Dépôt ─────────────────────────────────────────────────────────────────
if [[ $DEV_MODE -eq 1 ]] && [[ -f "$(dirname "$0")/fsdeploy/__init__.py" ]]; then
    # Mode développement : utiliser le répertoire courant
    INSTALL_DIR="$(cd "$(dirname "$0")" && pwd)"
    echo "▶ Mode DEV — répertoire local : $INSTALL_DIR"
else
    echo "▶ Clonage du dépôt..."
    if [[ -d "$INSTALL_DIR/.git" ]]; then
        git -C "$INSTALL_DIR" pull --quiet origin "$REPO_BRANCH"
        echo "  ✅ Dépôt mis à jour"
    else
        mkdir -p "$INSTALL_DIR"
        git clone --quiet --branch "$REPO_BRANCH" "$REPO_URL" "$INSTALL_DIR"
        echo "  ✅ Dépôt cloné → $INSTALL_DIR"
    fi
fi

# ── 4. Environnement virtuel Python ──────────────────────────────────────────
echo "▶ Création de l'environnement virtuel..."
python3 -m venv --system-site-packages "$VENV_DIR"
"$VENV_DIR/bin/pip" install --quiet --upgrade pip

echo "▶ Installation des dépendances Python..."
"$VENV_DIR/bin/pip" install --quiet -r "$INSTALL_DIR/requirements.txt"
echo "  ✅ Environnement Python prêt"

# ── 5. Lancement ─────────────────────────────────────────────────────────────
echo ""
echo "  ✅ Bootstrap terminé — lancement de fsdeploy"
echo ""
exec "$VENV_DIR/bin/python3" -m fsdeploy "$@"
