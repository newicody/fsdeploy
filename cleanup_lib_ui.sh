#!/bin/bash
# Script pour supprimer le dossier lib/ui/ redondant (tâche 7.10)

echo "Suppression du dossier lib/ui/..."
if [ -d "lib/ui" ]; then
    rm -rf lib/ui/
    echo "✅ Dossier lib/ui/ supprimé."
else
    echo "⚠️  Le dossier lib/ui/ n'existe pas ou a déjà été supprimé."
fi

echo ""
echo "Vérification des imports restants vers lib.ui.* ..."
grep -r "lib\.ui" . --include="*.py" 2>/dev/null | grep -v ".git" | head -10
if [ ${PIPESTATUS[0]} -eq 0 ]; then
    echo "⚠️  Certains fichiers contiennent encore 'lib.ui'."
else
    echo "✅ Aucun import détecté."
fi

exit 0
