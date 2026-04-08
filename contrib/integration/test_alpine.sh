#!/bin/sh
# Test d'intégration pour Alpine
# Vérifie l'environnement typique d'Alpine (musl, openrc).

set -e

echo "ALPINE_INTEGRATION_TEST: début" >&2
if [ -f /etc/os-release ]; then
    . /etc/os-release
    echo "DISTRO: $ID"
    echo "VERSION: $VERSION_ID"
else
    echo "DISTRO: unknown"
fi

echo "Kernel: $(uname -r)"
echo "Architecture: $(uname -m)"
echo "Libc: $(ldd --version 2>/dev/null | head -1 || echo 'musl')"

# Alpine utilise openrc par défaut
if [ -d /run/openrc ]; then
    echo "INIT: openrc"
else
    echo "INIT: autre"
fi

# Vérifier apk (gestionnaire de paquets)
if command -v apk >/dev/null 2>&1; then
    echo "PKG_MGR: apk"
else
    echo "PKG_MGR: non trouvé"
fi

echo "ALPINE_INTEGRATION_TEST: succès" >&2
exit 0
