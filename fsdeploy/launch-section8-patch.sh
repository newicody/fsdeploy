#!/usr/bin/env bash
# =============================================================================
# launch.sh — patch section 8 (VENV) et section 9 (VERIFICATION)
#
# Changements pour Textual 8.2.1 :
#   - textual-web n'est plus le point d'entrée
#   - textual + textual-dev sont les dépendances TUI
#   - textual serve remplace textual-web --app pour le mode navigateur
#
# Appliquer ce patch sur le launch.sh existant en remplaçant la section 8.
# =============================================================================

# ─────────────────────────────────────────────────────────────────────────────
# 8. ENVIRONNEMENT VIRTUEL PYTHON
# ─────────────────────────────────────────────────────────────────────────────
step "8/9 — Environnement virtuel Python"

if [[ ! -d "$VENV_DIR" ]]; then
    as_user python3 -m venv "$VENV_DIR"
    ok "Virtualenv cree → ${VENV_DIR}"
fi

# Upgrade pip et installer les outils de base
as_user "$VENV_DIR/bin/pip" install --quiet --upgrade pip setuptools wheel

# Installer les dépendances depuis requirements.txt
if [[ -f "${INSTALL_DIR}/requirements.txt" ]]; then
    as_user "$VENV_DIR/bin/pip" install --quiet -r "${INSTALL_DIR}/requirements.txt"
    ok "Dependances Python installees (Textual 8.x + Rich 14.x)"
else
    # Fallback : installer les dépendances minimales directement
    as_user "$VENV_DIR/bin/pip" install --quiet \
        "textual>=8.2.1,<9" \
        "textual-dev>=1.8.0,<2" \
        "rich>=14.3.3,<15" \
        "configobj>=5.0.8" \
        "typer>=0.12.0" \
        "structlog>=24.0.0" \
        "psutil>=5.9.0" \
        "pyudev>=0.24.0" \
        "packaging>=23.0" \
        "humanize>=4.0.0" \
        "watchfiles>=0.21.0" \
        "python-ffmpeg>=2.0.0"
    ok "Dependances Python installees (inline fallback)"
fi

# Vérification que Textual 8.x est bien installé
_textual_ver=$("$VENV_DIR/bin/python3" -c "import textual; print(textual.__version__)" 2>/dev/null || echo "MISSING")
if [[ "$_textual_ver" == "MISSING" ]]; then
    warn "Textual non installe correctement — verifiez requirements.txt"
elif [[ "${_textual_ver%%.*}" -lt 8 ]]; then
    warn "Textual $_textual_ver installe — version 8.x attendue"
else
    ok "Textual $_textual_ver installe"
fi

_rich_ver=$("$VENV_DIR/bin/python3" -c "import rich; print(rich.__version__)" 2>/dev/null || echo "MISSING")
if [[ "$_rich_ver" != "MISSING" ]]; then
    ok "Rich $_rich_ver installe"
fi

# Créer le wrapper /usr/local/bin/fsdeploy
if [[ ! -f "$WRAPPER" ]] || [[ $DEV_MODE -eq 1 ]]; then
    sudo tee "$WRAPPER" > /dev/null << WEOF
#!/bin/sh
# fsdeploy wrapper — genere par launch.sh
exec "${VENV_DIR}/bin/python3" -m fsdeploy "\$@"
WEOF
    sudo chmod 755 "$WRAPPER"
    ok "Wrapper installe → ${WRAPPER}"
fi

# Créer alias pour le mode web (remplace textual-web)
SERVE_WRAPPER="/usr/local/bin/fsdeploy-web"
if [[ ! -f "$SERVE_WRAPPER" ]] || [[ $DEV_MODE -eq 1 ]]; then
    sudo tee "$SERVE_WRAPPER" > /dev/null << WEOF
#!/bin/sh
# fsdeploy web mode — genere par launch.sh
# Usage : fsdeploy-web [--port 8080]
PORT="\${1:-8080}"
if [ "\$1" = "--port" ]; then PORT="\$2"; fi
exec "${VENV_DIR}/bin/textual" serve "python3 -m fsdeploy" --port "\$PORT"
WEOF
    sudo chmod 755 "$SERVE_WRAPPER"
    ok "Wrapper web installe → ${SERVE_WRAPPER}"
fi

# Écrire le fichier .env
as_user bash -c "cat > '${ENV_FILE}'" << ENVEOF
# fsdeploy — variables d'environnement
# Genere par launch.sh — $(date '+%Y-%m-%d %H:%M:%S')
FSDEPLOY_USER="${REAL_USER}"
FSDEPLOY_GROUP="${FSDEPLOY_GROUP}"
FSDEPLOY_INSTALL_DIR="${INSTALL_DIR}"
FSDEPLOY_VENV="${VENV_DIR}"
FSDEPLOY_LOG_DIR="${LOG_DIR}"
FSDEPLOY_TEXTUAL_VERSION="${_textual_ver}"
FSDEPLOY_RICH_VERSION="${_rich_ver}"
ENVEOF
srun chmod 640 "$ENV_FILE"
srun chown "${REAL_USER}:${FSDEPLOY_GROUP}" "$ENV_FILE"
ok ".env genere"
