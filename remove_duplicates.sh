#!/bin/bash
# Supprimer les écrans doublons (10.5)
set -e
cd "$(dirname "$0")" || exit 1
echo "Suppression des doublons..."
rm -f fsdeploy/lib/ui/screens/graph_enhanced.py
rm -f fsdeploy/lib/ui/screens/security_enhanced.py
rm -f fsdeploy/lib/ui/screens/navigation.py
rm -f fsdeploy/lib/ui/screens/multiarch_screen.py
echo "Fichiers supprimés."
# Vérifier qu'il n'y a plus de références
if grep -r "graph_enhanced\|security_enhanced\|NavigationScreen" fsdeploy/lib/ui/screens/ 2>/dev/null; then
    echo "ATTENTION: références restantes."
else
    echo "Aucune référence trouvée."
fi
