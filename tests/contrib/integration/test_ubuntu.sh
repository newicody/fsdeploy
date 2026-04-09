#!/bin/sh
# Test d'intégration pour Ubuntu
# Similaire à Debian mais avec snapd éventuel.

set -e

echo "UBUNTU_INTEGRATION_TEST: début" >&2
if [ -f /etc/os-release ]; then
    . /etc/os-release
    echo "DISTRO: $ID"
    echo "VERSION: $VERSION_ID"
    echo "CODENAME: $VERSION_CODENAME"
else
    echo "DISTRO: unknown"
fi

echo "Kernel: $(uname -r)"
echo "Architecture: $(uname -m)"

# Vérifier systemd (Ubuntu moderne)
if command -v systemctl >/dev/null 2>&1; then
    echo "INIT: systemd"
else
    echo "INIT: autre"
fi

# Vérifier snap
if command -v snap >/dev/null 2>&1; then
    echo "SNAP: présent"
else
    echo "SNAP: absent"
fi

echo "UBUNTU_INTEGRATION_TEST: succès" >&2
exit 0
