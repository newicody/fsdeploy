#!/bin/sh
# Test d'intégration pour Arch Linux
# Vérifie systemd et pacman.

set -e

echo "ARCH_INTEGRATION_TEST: début" >&2
if [ -f /etc/os-release ]; then
    . /etc/os-release
    echo "DISTRO: $ID"
    echo "VERSION: $VERSION_ID"
else
    echo "DISTRO: unknown"
fi

echo "Kernel: $(uname -r)"
echo "Architecture: $(uname -m)"

# Arch utilise systemd
if command -v systemctl >/dev/null 2>&1; then
    echo "INIT: systemd"
else
    echo "INIT: non systemd"
fi

# Vérifier pacman
if command -v pacman >/dev/null 2>&1; then
    echo "PKG_MGR: pacman"
else
    echo "PKG_MGR: non trouvé"
fi

echo "ARCH_INTEGRATION_TEST: succès" >&2
exit 0
