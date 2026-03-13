#!/bin/bash
# =============================================================================
# lib/python-sfs.sh — Construction de python-<ver>-<YYYYMMDD>.sfs
#
# Produit :
#   python-<ver>-<YYYYMMDD>.sfs          images/startup/
#   python-<ver>-<YYYYMMDD>.sfs.meta
#
# Variables :
#   IMAGE_DATE   YYYYMMDD (défaut : aujourd'hui)
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/naming.sh"

GREEN='\033[1;32m'; YELLOW='\033[1;33m'; RED='\033[1;31m'; NC='\033[0m'
ok()   { echo -e "  ${GREEN}✅ $*${NC}"; }
warn() { echo -e "  ${YELLOW}⚠️  $*${NC}"; }
err()  { echo -e "  ${RED}❌ $*${NC}"; exit 1; }

# Localisation de boot_pool — utilise zbm_locate_boot() de naming.sh
# Sur Debian live /boot est occupé → boot_pool monté sur ${ZBM_BOOT:-/mnt/zbm/boot}
_MOUNTED_BOOT=0  # rétrocompat
_cleanup_boot() { zbm_cleanup_boot; }
trap _cleanup_boot EXIT
zbm_locate_boot || err "boot_pool introuvable — vérifiez les pools ZFS"
TODAY="${IMAGE_DATE:-$(date +%Y%m%d)}"
WORK="/tmp/python-sfs-build-$$"

PYTHON_BIN=$(command -v python3 || err "python3 introuvable")
PYTHON_VER=$("$PYTHON_BIN" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PYTHON_FULL=$("$PYTHON_BIN" --version 2>&1 | awk '{print $2}')

PYTHON_SFS=$(zbm_path python "" "$PYTHON_VER" "$TODAY")
mkdir -p "$(zbm_dir python)"

echo "  Python : $PYTHON_BIN  v${PYTHON_FULL}"
echo "  Cible  : $(basename "$PYTHON_SFS")"

if [[ -f "$PYTHON_SFS" ]]; then
    echo -n "  $(basename "$PYTHON_SFS") existe. Reconstruire ? [o/N] : "
    read -r R
    [[ "$R" =~ ^[Oo]$ ]] || { ok "SFS existant conservé"; exit 0; }
fi

# =============================================================================
# 1. BUILD DIR
# =============================================================================
rm -rf "$WORK"
mkdir -p "$WORK"/{bin,etc/zfsbootmenu}

# =============================================================================
# 2. VENV + TEXTUAL
# =============================================================================
echo "  Installation de Textual dans le venv..."
VENV="$WORK/venv"
python3 -m venv "$VENV"
"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet textual
ok "Textual installé"

# =============================================================================
# 3. INTERFACE PYTHON
# =============================================================================
IFACE_SRC=""
for candidate in \
    "$(dirname "$SCRIPT_DIR")/python-interface.py" \
    "/etc/zfsbootmenu/python_interface.py" \
    "${BOOT}/python_interface.py"; do   # BOOT détecté dynamiquement ci-dessus
    [[ -f "$candidate" ]] && { IFACE_SRC="$candidate"; break; }
done

if [[ -n "$IFACE_SRC" ]]; then
    cp "$IFACE_SRC" "$WORK/etc/zfsbootmenu/python_interface.py"
    ok "Interface : $(basename "$IFACE_SRC")"
else
    warn "Interface Python introuvable — placeholder"
    printf '#!/usr/bin/env python3\nprint("ZBM interface — à remplacer")\ninput()\n' \
        > "$WORK/etc/zfsbootmenu/python_interface.py"
fi

# =============================================================================
# 4. LAUNCHER
# =============================================================================
cat > "$WORK/launch.sh" << 'LAUNCH'
#!/bin/sh
VENV="/mnt/python/venv"
IFACE="/mnt/python/etc/zfsbootmenu/python_interface.py"
export PATH="$VENV/bin:$PATH"
export TERM="${TERM:-linux}"
export COLORTERM="truecolor"
exec "$VENV/bin/python3" "$IFACE" "$@"
LAUNCH
chmod +x "$WORK/launch.sh"

# =============================================================================
# 5. SQUASHFS
# =============================================================================
echo -n "  Construction $(basename "$PYTHON_SFS")..."
mksquashfs "$WORK" "$PYTHON_SFS" \
    -comp zstd -Xcompression-level 6 -noappend -quiet \
    -e "${VENV}/lib/python${PYTHON_VER}/site-packages/pip"       \
    -e "${VENV}/lib/python${PYTHON_VER}/site-packages/setuptools"
chmod 444 "$PYTHON_SFS"
echo " OK  ($(du -sh "$PYTHON_SFS" | cut -f1))"

rm -rf "$WORK"

# =============================================================================
# 6. META
# =============================================================================
zbm_write_meta "$PYTHON_SFS" \
    "kernel_ver=" \
    "builder=python-sfs.sh"

ok "$(basename "$PYTHON_SFS")"
echo "  Monté au boot sur /mnt/python  (launch.sh disponible)"
