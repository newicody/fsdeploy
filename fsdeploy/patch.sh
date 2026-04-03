#!/usr/bin/env bash
# =============================================================================
# fix-screen-names.sh — Supprime self.name = "..." des écrans Textual
#
# Textual 8.x a rendu Screen.name en property read-only.
# Les noms sont déjà gérés par app.install_screen(cls, name=name).
#
# Usage : cd /opt/fsdeploy && bash fix-screen-names.sh
# =============================================================================
set -euo pipefail

SCREENS_DIR="${1:-fsdeploy/lib/ui/screens}"

if [[ ! -d "$SCREENS_DIR" ]]; then
    echo "Dossier $SCREENS_DIR introuvable"
    echo "Usage: bash $0 [chemin/vers/screens/]"
    exit 1
fi

count=0

for f in "$SCREENS_DIR"/*.py; do
    [[ -f "$f" ]] || continue
    
    # Chercher les lignes self.name = "..." ou self.name="..."
    if grep -qE '^\s*self\.name\s*=\s*["\x27]' "$f"; then
        # Supprimer la ligne
        sed -i '/^\s*self\.name\s*=\s*["\x27]/d' "$f"
        echo "  ✅  $(basename "$f") — self.name supprimé"
        (( count++ )) || true
    fi
done

# Aussi vérifier s'il y a un doublon dans ui/screens/ à la racine du repo
ALT_DIR="${SCREENS_DIR/fsdeploy\/lib/}"
if [[ -d "$ALT_DIR" && "$ALT_DIR" != "$SCREENS_DIR" ]]; then
    for f in "$ALT_DIR"/*.py; do
        [[ -f "$f" ]] || continue
        if grep -qE '^\s*self\.name\s*=\s*["\x27]' "$f"; then
            sed -i '/^\s*self\.name\s*=\s*["\x27]/d' "$f"
            echo "  ✅  $(basename "$f") (alt) — self.name supprimé"
            (( count++ )) || true
        fi
    done
fi

echo ""
echo "  $count fichier(s) corrigé(s)"
echo ""
echo "  Les noms d'écrans sont gérés par app.install_screen(cls, name=name)"
echo "  dans _register_screens(). Pas besoin de self.name dans les screens."
