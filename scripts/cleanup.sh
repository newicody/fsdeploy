#!/bin/bash
set -euo pipefail

echo "=== Nettoyage et vérification des tests ==="
echo ""

# Suppression des fichiers obsolètes
echo "1. Suppression du stub cross_compile_screen.py..."
if [ -f "fsdeploy/lib/ui/screens/cross_compile_screen.py" ]; then
    rm -v "fsdeploy/lib/ui/screens/cross_compile_screen.py"
else
    echo "   fichier introuvable, ignoré."
fi

echo ""
echo "2. Suppression de CLEANUP.md (s'il existe)..."
rm -f "CLEANUP.md" && echo "   supprimé." || echo "   absent, ignoré."

echo ""
echo "3. Lancement rapide des tests pour détecter les erreurs d'import..."
python -m pytest tests/ -xvs --tb=short 2>&1 | head -80

echo ""
echo "=== Fin du script cleanup.sh ==="
