#!/usr/bin/env bash
# =============================================================================
# fix-all.sh — Correctifs fsdeploy post-bootstrap
#
# Usage : cd /opt/fsdeploy && bash fix-all.sh
# =============================================================================
set -euo pipefail

REPO="${1:-.}"

ok()   { printf "  \033[32m✅  %s\033[0m\n" "$*"; }
info() { printf "  \033[36m→   %s\033[0m\n" "$*"; }
warn() { printf "  \033[33m⚠   %s\033[0m\n" "$*"; }

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║         fsdeploy — correctifs globaux            ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# ─────────────────────────────────────────────────────────────────
# 1. LAUNCH.SH — linux-headers-$(uname -r)
# ─────────────────────────────────────────────────────────────────
info "Fix 1/4 : linux-headers"
if [[ -f "$REPO/launch.sh" ]]; then
    sed -i 's/linux-headers-amd64/linux-headers-$(uname -r)/g' "$REPO/launch.sh"
    ok "launch.sh corrigé"
fi

KVER="$(uname -r)"
if ! dpkg -l "linux-headers-$KVER" 2>/dev/null | grep -q '^ii'; then
    info "Installation linux-headers-$KVER..."
    sudo apt-get install -y -qq "linux-headers-$KVER" 2>/dev/null && \
        ok "linux-headers-$KVER installé" || warn "Echec"
else
    ok "linux-headers-$KVER OK"
fi

# ─────────────────────────────────────────────────────────────────
# 2. SCREENS — supprimer TOUS les self.name = "..."
# ─────────────────────────────────────────────────────────────────
info "Fix 2/4 : self.name (Textual 8.x)"

count=0
for dir in "$REPO"/*/lib/ui/screens "$REPO"/lib/ui/screens "$REPO"/ui/screens; do
    [[ -d "$dir" ]] || continue
    for f in "$dir"/*.py; do
        [[ -f "$f" ]] || continue
        if grep -qP 'self\.name\s*=' "$f"; then
            sed -i '/^\s*self\.name\s*=/d' "$f"
            ok "$(basename "$f")"
            (( count++ )) || true
        fi
    done
done
[[ $count -eq 0 ]] && ok "Aucun restant" || ok "$count fichier(s)"

# ─────────────────────────────────────────────────────────────────
# 3. POOL IMPORT — zpool import -af -N avant détection
# ─────────────────────────────────────────────────────────────────
info "Fix 3/4 : auto-import pools"

LIB_DIR=""
for d in "$REPO/fsdeploy/lib" "$REPO/lib"; do
    [[ -d "$d/intents" ]] && LIB_DIR="$d" && break
done

if [[ -n "$LIB_DIR" ]]; then
    DI="$LIB_DIR/intents/detection_intent.py"
    DS="$LIB_DIR/ui/screens/detection.py"

    # 3a. Ajouter PoolImportAllTask + Intent
    if [[ -f "$DI" ]] && ! grep -q 'PoolImportAllTask' "$DI"; then
        cat >> "$DI" << 'PYEOF'


# ═══════════════════════════════════════════════════════════════════
# IMPORT AUTO — zpool import -af -N avant toute détection
# ═══════════════════════════════════════════════════════════════════

@security.detect.probe
class PoolImportAllTask(Task):
    """Importe tous les pools avec -af -N."""

    def run(self) -> dict[str, Any]:
        self.run_cmd("zpool import -af -N -o cachefile=none",
                     sudo=True, check=False)
        r = self.run_cmd("zpool list -H -o name", sudo=True, check=False)
        pools = [p.strip() for p in r.stdout.splitlines() if p.strip()]
        return {"imported_pools": pools}


@register_intent("pool.import_all")
class PoolImportAllIntent(Intent):
    """Event: pool.import_all → PoolImportAllTask"""
    def build_tasks(self):
        return [PoolImportAllTask(
            id="import_all", params={}, context=self.context)]
PYEOF
        ok "PoolImportAllTask ajouté"
    else
        ok "PoolImportAllTask déjà présent"
    fi

    # 3b. Injecter pool.import_all dans DetectionScreen
    if [[ -f "$DS" ]] && ! grep -q 'pool.import_all' "$DS"; then
        python3 - "$DS" << 'PYFIX'
import sys

path = sys.argv[1]
with open(path, "r") as f:
    lines = f.readlines()

out = []
injected = False
for line in lines:
    # Chercher la ligne qui émet pool.status
    if not injected and 'bridge.emit("pool.status"' in line:
        indent = line[:len(line) - len(line.lstrip())]
        out.append(f'{indent}# Import auto de tous les pools\n')
        out.append(f'{indent}self.bridge.emit("pool.import_all",\n')
        out.append(f'{indent}                 callback=lambda t: self._safe_log(\n')
        out.append(f'{indent}                     f"  {{CHECK}} Pools importes" if t.status == "completed"\n')
        out.append(f'{indent}                     else f"  {{WARN}} Import: {{t.error}}"))\n')
        out.append(f'{indent}self._log("  -> pool.import_all")\n')
        out.append(f'\n')
        injected = True
    out.append(line)

with open(path, "w") as f:
    f.writelines(out)

if injected:
    print("  OK")
else:
    print("  WARN: pattern non trouvé")
PYFIX
        ok "DetectionScreen: pool.import_all avant pool.status"
    else
        ok "DetectionScreen déjà corrigé"
    fi
else
    warn "lib/ non trouvé"
fi

# ─────────────────────────────────────────────────────────────────
# 4. WEB SERVER
# ─────────────────────────────────────────────────────────────────
info "Fix 4/4 : fsdeploy-web"

VENV_DIR="$REPO/.venv"
[[ ! -d "$VENV_DIR" ]] && VENV_DIR="$REPO/fsdeploy/.venv"

if [[ -x "$VENV_DIR/bin/python3" ]]; then
    # S'assurer que textual-dev est installé (contient textual serve)
    if ! "$VENV_DIR/bin/python3" -c "import textual_dev" 2>/dev/null; then
        info "Installation textual-dev..."
        "$VENV_DIR/bin/pip" install --quiet "textual-dev>=1.8.0,<2" && \
            ok "textual-dev installé" || warn "Echec install textual-dev"
    fi

    sudo tee /usr/local/bin/fsdeploy-web > /dev/null << WEBEOF
#!/usr/bin/env bash
# fsdeploy web — généré par fix-all.sh
[ -f "$REPO/.env" ] && . "$REPO/.env"
PORT="\${1:-8080}"
[ "\$1" = "--port" ] && PORT="\$2"
exec $VENV_DIR/bin/textual serve \\
    --port "\$PORT" --host 0.0.0.0 \\
    "$VENV_DIR/bin/python3 -m fsdeploy"
WEBEOF
    sudo chmod 755 /usr/local/bin/fsdeploy-web
    ok "fsdeploy-web configuré"
else
    warn "Venv absent"
fi

# ─────────────────────────────────────────────────────────────────
# NETTOYAGE
# ─────────────────────────────────────────────────────────────────
info "Nettoyage fichiers stale"
for s in bus/init.py ARCHITECTURE.py scheduler/intentlog/huffman.py \
         scheduler/core/intent.py; do
    f="$LIB_DIR/$s"
    [[ -f "$f" ]] && rm -f "$f" && ok "$(basename "$f")"
done
[[ -f "$REPO/launch-section8-patch.sh" ]] && rm -f "$REPO/launch-section8-patch.sh" && ok "launch-section8-patch.sh"

echo ""
echo "  ✅  Terminé. Relancer : fsdeploy"
echo ""
