#!/usr/bin/env bash
# =============================================================================
# install-fix.sh — Applique les corrections fsdeploy
#
# Usage : bash install-fix.sh /opt/fsdeploys/fsdeploys/fsdeploy/lib
# =============================================================================
set -euo pipefail

GREEN="\033[32m" RED="\033[31m" YELLOW="\033[33m" CYAN="\033[36m" RST="\033[0m"
ok()   { printf "${GREEN}  OK   %s${RST}\n" "$*"; }
fail() { printf "${RED}  FAIL %s${RST}\n" "$*"; }
warn() { printf "${YELLOW}  WARN %s${RST}\n" "$*"; }
info() { printf "${CYAN}  -->  %s${RST}\n" "$*"; }

LIB="${1:-}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [[ -z "$LIB" ]]; then
    # Auto-detect
    for candidate in \
        "/opt/fsdeploys/fsdeploys/fsdeploy/lib" \
        "/opt/fsdeploy/fsdeploy/lib" \
        "/opt/fsdeploy/lib"; do
        [[ -d "$candidate/ui/screens" ]] && LIB="$candidate" && break
    done
fi

if [[ -z "$LIB" || ! -d "$LIB/ui/screens" ]]; then
    echo "Usage: bash install-fix.sh /chemin/vers/fsdeploy/lib"
    echo "  Le repertoire doit contenir ui/screens/"
    exit 1
fi

echo ""
echo "=== fsdeploy fix — cible: $LIB ==="
echo ""

# ─────────────────────────────────────────────────────────────────
# 1. Copier les fichiers corriges
# ─────────────────────────────────────────────────────────────────
info "Copie des fichiers corriges"

cp "$SCRIPT_DIR/lib/daemon.py" "$LIB/daemon.py"
ok "daemon.py"

cp "$SCRIPT_DIR/lib/intents/detection_intent.py" "$LIB/intents/detection_intent.py"
ok "intents/detection_intent.py"

cp "$SCRIPT_DIR/lib/ui/screens/detection.py" "$LIB/ui/screens/detection.py"
ok "ui/screens/detection.py"

cp "$SCRIPT_DIR/lib/ui/screens/mounts.py" "$LIB/ui/screens/mounts.py"
ok "ui/screens/mounts.py"

# ─────────────────────────────────────────────────────────────────
# 2. Purger TOUS les __pycache__ (evite les .pyc stale)
# ─────────────────────────────────────────────────────────────────
info "Purge __pycache__"

count=$(find "$LIB" -type d -name __pycache__ | wc -l)
find "$LIB" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
ok "$count repertoire(s) __pycache__ purge(s)"

# Aussi purger dans le repo parent
REPO="$(dirname "$LIB")"
find "$REPO" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# ─────────────────────────────────────────────────────────────────
# 3. Detecter les repertoires ui/screens/ en doublon
# ─────────────────────────────────────────────────────────────────
info "Verification doublons"

# Verifier s'il y a un ui/screens/ EN DEHORS de lib/
PARENT="$(dirname "$LIB")"
if [[ -d "$PARENT/ui/screens" && "$PARENT/ui/screens" != "$LIB/ui/screens" ]]; then
    warn "Doublon detecte: $PARENT/ui/screens/"
    warn "  -> Ce repertoire peut causer des imports incorrects"
    warn "  -> Supprimez-le: rm -rf $PARENT/ui/screens"
else
    ok "Pas de doublon ui/screens/"
fi

# ─────────────────────────────────────────────────────────────────
# 4. Detecter les fichiers avec encodage casse (bug web UTF-8)
# ─────────────────────────────────────────────────────────────────
info "Verification encodage UTF-8"

bad_files=0
while IFS= read -r -d '' pyfile; do
    if ! python3 -c "open('$pyfile', encoding='utf-8').read()" 2>/dev/null; then
        fail "Encodage casse: $pyfile"
        bad_files=$((bad_files + 1))
    fi
done < <(find "$LIB" -name "*.py" -print0)

if [[ $bad_files -eq 0 ]]; then
    ok "Tous les .py sont UTF-8 valides"
else
    warn "$bad_files fichier(s) avec encodage casse"
    warn "  -> Corrigez avec: iconv -f latin1 -t utf-8 fichier.py > fichier_fix.py"
fi

# ─────────────────────────────────────────────────────────────────
# 5. Verifier self.name residuel dans les screens
# ─────────────────────────────────────────────────────────────────
info "Verification self.name (Textual 8.x)"

selfname_count=0
for f in "$LIB"/ui/screens/*.py; do
    [[ -f "$f" ]] || continue
    if grep -qP 'self\.name\s*=\s*["\x27]' "$f"; then
        warn "self.name dans $(basename "$f") — a supprimer"
        # Supprimer automatiquement
        sed -i '/self\.name\s*=\s*["\x27]/d' "$f"
        ok "  -> corrige automatiquement"
        selfname_count=$((selfname_count + 1))
    fi
done

if [[ $selfname_count -eq 0 ]]; then
    ok "Aucun self.name residuel"
fi

# ─────────────────────────────────────────────────────────────────
# 6. Verifier les fichiers stale
# ─────────────────────────────────────────────────────────────────
info "Verification fichiers stale"

for stale in "ARCHITECTURE.py" "scheduler/intentlog/huffman.py" \
             "scheduler/core/intent.py" "bus/init.py"; do
    p="$LIB/$stale"
    if [[ -f "$p" ]]; then
        rm -f "$p"
        ok "Supprime: $stale"
    fi
done

# ─────────────────────────────────────────────────────────────────
# 7. Verifier daemon.py pas corrompu
# ─────────────────────────────────────────────────────────────────
info "Verification daemon.py"

if head -1 "$LIB/daemon.py" | grep -q "^{"; then
    fail "daemon.py contient du JSON — CORROMPU"
else
    ok "daemon.py est du Python valide"
fi

if grep -q "store=self._store" "$LIB/daemon.py"; then
    fail "daemon.py contient store=self._store (kwarg invalide)"
else
    ok "daemon.py Executor() correct"
fi

# ─────────────────────────────────────────────────────────────────
# Resultat
# ─────────────────────────────────────────────────────────────────
echo ""
echo "=== Installation terminee ==="
echo ""
echo "Lancez maintenant :"
echo "  cd $(dirname "$LIB")"
echo "  $(dirname "$LIB")/../.venv/bin/python3 -m fsdeploy --debug"
echo ""
echo "Mode web :"
echo '  PYTHONIOENCODING=utf-8 textual serve --port 8080 --host 0.0.0.0 \'
echo "    \"$(dirname "$LIB")/../.venv/bin/python3 -m fsdeploy\""
echo ""
