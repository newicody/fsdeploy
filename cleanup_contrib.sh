#!/bin/bash
set -euo pipefail

echo "Nettoyage et centralisation de contrib/ (tâche 7.9)"

# Déplacer les scripts de test
if [[ -d "contrib/integration" ]]; then
    mkdir -p fsdeploy/contrib/integration
    if ls contrib/integration/test_*.sh >/dev/null 2>&1; then
        mv -v contrib/integration/test_*.sh fsdeploy/contrib/integration/
    fi
fi

# Déplacer les scripts OpenRC
if [[ -f "contrib/fsdeploy.init" ]]; then
    mkdir -p fsdeploy/contrib/openrc
    mv -v contrib/fsdeploy.init fsdeploy/contrib/openrc/
fi
if [[ -f "contrib/fsdeploy.initd" ]]; then
    mkdir -p fsdeploy/contrib/openrc
    mv -v contrib/fsdeploy.initd fsdeploy/contrib/openrc/
fi

# Déplacer le service systemd
if [[ -f "contrib/fsdeploy.service" ]]; then
    mkdir -p fsdeploy/contrib/systemd
    mv -v contrib/fsdeploy.service fsdeploy/contrib/systemd/
fi

# Supprimer les fichiers redondants
if [[ -f "contrib/sysvinit/fsdeploy" ]]; then
    rm -v "contrib/sysvinit/fsdeploy"
fi
if [[ -f "contrib/upstart/fsdeploy.conf" ]]; then
    rm -v "contrib/upstart/fsdeploy.conf"
fi

# Supprimer les dossiers vides de contrib/
find contrib -type d -empty -delete 2>/dev/null || true

# Si contrib/ est vide, le supprimer
if [[ -d "contrib" ]] && [[ -z "$(ls -A contrib 2>/dev/null)" ]]; then
    rmdir -v contrib
fi

echo "Tâche 7.9 terminée."
