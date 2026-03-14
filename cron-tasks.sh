#!/bin/bash
# =============================================================================
# cron-tasks.sh
# Installation du service zbm-startup et des tâches cron dans un rootfs cible.
#
# À lancer depuis la machine de déploiement (live Debian) une fois
# le rootfs monté sur $MOUNTPOINT.
# Les snapshots sont gérés par fsdeploy directement (UI + CLI),
# ce script installe uniquement la planification cron et le service.
#
# Usage :
#   MOUNTPOINT=/mnt/gentoo bash cron-tasks.sh
# =============================================================================

set -euo pipefail

RED='\033[1;31m'; GREEN='\033[1;32m'; YELLOW='\033[1;33m'
BLUE='\033[1;34m'; BOLD='\033[1m'; NC='\033[0m'

ok()   { echo -e "   ${GREEN}✅ $*${NC}"; }
warn() { echo -e "   ${YELLOW}⚠️  $*${NC}"; }
err()  { echo -e "   ${RED}❌ $*${NC}"; exit 1; }
step() { echo -e "\n${BLUE}${BOLD}▶ $*${NC}"; }
info() { echo -e "   ${BLUE}ℹ  $*${NC}"; }

[[ $EUID -ne 0 ]] && err "Root requis."

MOUNTPOINT="${MOUNTPOINT:-/mnt/gentoo}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# SCRIPT_DIR = racine du dépôt fsdeploy (là où se trouvent launch.sh et system/)
SYSTEM_DIR="${SCRIPT_DIR}/system"

[[ -d "$MOUNTPOINT" ]] || err "MOUNTPOINT introuvable : $MOUNTPOINT"
[[ -d "$SYSTEM_DIR" ]] || err "Répertoire system/ introuvable : $SYSTEM_DIR"

# =============================================================================
# 1. CRON — planification des snapshots fsdeploy
# =============================================================================
step "Installation du fichier cron"

# Le cron appelle fsdeploy en mode CLI.
# fsdeploy doit être installé dans le rootfs cible ou accessible via le venv.
# Si ce n'est pas le cas, adapter le chemin FSDEPLOY_CMD.
FSDEPLOY_CMD="/opt/fsdeploy/.venv/bin/python3 -m fsdeploy"

cat > "$MOUNTPOINT/etc/cron.d/fsdeploy-snapshots" << CRON
# fsdeploy — Snapshots planifiés
# Vérification toutes les heures (fsdeploy décide lui-même si un profil est échu)
0 * * * *   root   ${FSDEPLOY_CMD} snapshot --run-scheduled >> /var/log/fsdeploy-cron.log 2>&1

# Archivage mensuel automatique (1er du mois à 5h)
0 5 1 * *   root   ${FSDEPLOY_CMD} snapshot --archive-monthly >> /var/log/fsdeploy-cron.log 2>&1
CRON
ok "/etc/cron.d/fsdeploy-snapshots"

# =============================================================================
# 2. LOGROTATE
# =============================================================================
step "Logrotate"

cat > "$MOUNTPOINT/etc/logrotate.d/fsdeploy" << 'LR'
/var/log/fsdeploy-cron.log
/var/log/zbm-startup.log
{
    weekly
    rotate 8
    compress
    delaycompress
    missingok
    notifempty
    create 640 root root
}
LR
ok "logrotate fsdeploy"

# =============================================================================
# 3. SERVICE zbm-startup (systemd / OpenRC / sysvinit)
# =============================================================================
step "Service zbm-startup"

# ── Détection de l'init dans le rootfs CIBLE ─────────────────────────────────
_detect_target_init() {
    if [[ -x "${MOUNTPOINT}/sbin/openrc" ]] || \
       [[ -x "${MOUNTPOINT}/sbin/openrc-init" ]] || \
       [[ -f "${MOUNTPOINT}/etc/gentoo-release" ]] || \
       [[ -f "${MOUNTPOINT}/etc/alpine-release" ]]; then
        echo "openrc"
    elif [[ -d "${MOUNTPOINT}/etc/systemd" ]] || \
         [[ -x "${MOUNTPOINT}/lib/systemd/systemd" ]] || \
         [[ -x "${MOUNTPOINT}/usr/lib/systemd/systemd" ]]; then
        echo "systemd"
    elif [[ -d "${MOUNTPOINT}/etc/init.d" ]]; then
        echo "sysvinit"
    else
        echo "unknown"
    fi
}

TARGET_INIT=$(_detect_target_init)
info "Init détecté dans le rootfs cible : ${TARGET_INIT}"

case "$TARGET_INIT" in

    openrc)
        SRC="${SYSTEM_DIR}/zbm-startup"
        [[ -f "$SRC" ]] || err "system/zbm-startup introuvable"
        install -m 0755 "$SRC" "${MOUNTPOINT}/etc/init.d/zbm-startup"
        ok "zbm-startup installé (OpenRC)"

        if chroot "${MOUNTPOINT}" which rc-update >/dev/null 2>&1; then
            chroot "${MOUNTPOINT}" rc-update add zbm-startup default 2>/dev/null \
                && ok "rc-update add zbm-startup default" \
                || warn "Activation manuelle requise : rc-update add zbm-startup default"
        fi
        ;;

    systemd)
        SRC="${SYSTEM_DIR}/zbm-startup.service"
        [[ -f "$SRC" ]] || err "system/zbm-startup.service introuvable"
        install -m 0644 "$SRC" "${MOUNTPOINT}/etc/systemd/system/zbm-startup.service"
        ok "zbm-startup.service installé (systemd)"

        if chroot "${MOUNTPOINT}" which systemctl >/dev/null 2>&1; then
            chroot "${MOUNTPOINT}" systemctl enable zbm-startup 2>/dev/null \
                && ok "systemctl enable zbm-startup" \
                || warn "Activation manuelle requise : systemctl enable zbm-startup"
        fi
        ;;

    sysvinit)
        SRC="${SYSTEM_DIR}/zbm-startup.init.d"
        [[ -f "$SRC" ]] || SRC="${SYSTEM_DIR}/zbm-startup"   # fallback OpenRC
        [[ -f "$SRC" ]] || err "Aucun script sysvinit trouvé dans system/"
        install -m 0755 "$SRC" "${MOUNTPOINT}/etc/init.d/zbm-startup"
        ok "zbm-startup installé (sysvinit)"

        if chroot "${MOUNTPOINT}" which update-rc.d >/dev/null 2>&1; then
            chroot "${MOUNTPOINT}" update-rc.d zbm-startup defaults 2>/dev/null \
                && ok "update-rc.d zbm-startup defaults" \
                || warn "Activation manuelle requise : update-rc.d zbm-startup defaults"
        elif chroot "${MOUNTPOINT}" which chkconfig >/dev/null 2>&1; then
            chroot "${MOUNTPOINT}" chkconfig zbm-startup on 2>/dev/null \
                && ok "chkconfig zbm-startup on" \
                || warn "Activation manuelle requise : chkconfig zbm-startup on"
        else
            warn "Aucun outil d'activation trouvé — activation manuelle requise"
        fi
        ;;

    *)
        warn "Init non reconnu — installation manuelle du service requise"
        warn "Fichiers disponibles dans system/ :"
        warn "  zbm-startup          → OpenRC  → /etc/init.d/zbm-startup"
        warn "  zbm-startup.service  → systemd → /etc/systemd/system/"
        warn "  zbm-startup.init.d   → sysvinit → /etc/init.d/zbm-startup"
        ;;
esac

# =============================================================================
# RÉSUMÉ
# =============================================================================
echo ""
echo -e "${GREEN}${BOLD}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║         ✅  fsdeploy — tâches installées                    ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo "  Cron : /etc/cron.d/fsdeploy-snapshots"
echo "    0 * * * *  fsdeploy snapshot --run-scheduled"
echo "    0 5 1 * *  fsdeploy snapshot --archive-monthly"
echo ""
echo "  Service zbm-startup : ${TARGET_INIT}"
echo ""
echo "  Logs :"
echo "    /var/log/fsdeploy-cron.log"
echo "    /var/log/zbm-startup.log"
echo "    (rotation hebdo, 8 semaines)"
echo ""
