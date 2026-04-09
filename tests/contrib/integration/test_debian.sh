#!/bin/sh
# Test d'intégration pour Debian
# Vérifie la présence des outils système nécessaires à fsdeploy.

set -e

echo "DEBIAN_INTEGRATION_TEST: début" >&2
if [ -f /etc/os-release ]; then
    . /etc/os-release
    echo "DISTRO: $ID"
    echo "VERSION: $VERSION_ID"
else
    echo "DISTRO: unknown"
fi

# Vérifications basiques
echo "Kernel: $(uname -r)"
echo "Architecture: $(uname -m)"

# Vérifier que ZFS est chargé (optionnel)
if lsmod | grep -q zfs; then
    echo "ZFS: présent"
else
    echo "ZFS: absent (non critique)"
fi

# Vérifier que systemd ou openrc est présent (selon init)
if command -v systemctl >/dev/null 2>&1; then
    echo "INIT: systemd"
elif [ -d /run/openrc ]; then
    echo "INIT: openrc"
else
    echo "INIT: autre"
fi

echo "DEBIAN_INTEGRATION_TEST: succès" >&2
exit 0
