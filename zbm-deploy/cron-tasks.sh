#!/bin/bash
# =============================================================================
# cron-tasks.sh
# Installation des wrappers cron pour les snapshots planifiés
#
# Les planifications sont définies dans l'UI Python (profiles.json).
# Le cron ne fait qu'appeler zbm-run-scheduled.py toutes les heures ;
# c'est le script Python qui décide si un profil est à exécuter.
#
# Usage : bash cron-tasks.sh
# =============================================================================

set -euo pipefail

RED='\033[1;31m'; GREEN='\033[1;32m'; YELLOW='\033[1;33m'
BLUE='\033[1;34m'; BOLD='\033[1m'; NC='\033[0m'

ok()   { echo -e "   ${GREEN}✅ $*${NC}"; }
warn() { echo -e "   ${YELLOW}⚠️  $*${NC}"; }
err()  { echo -e "   ${RED}❌ $*${NC}"; exit 1; }
step() { echo -e "\n${BLUE}${BOLD}▶ $*${NC}"; }

[[ $EUID -ne 0 ]] && err "Root requis."
MOUNTPOINT="${MOUNTPOINT:-/mnt/gentoo}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# =============================================================================
# 1. SCRIPT PYTHON POUR LES SNAPSHOTS PLANIFIÉS
# =============================================================================
step "Création de zbm-run-scheduled.py"

cat > "$MOUNTPOINT/usr/local/bin/zbm-run-scheduled.py" << 'PYEOF'
#!/usr/bin/env python3
# =============================================================================
# zbm-run-scheduled.py
# Exécuté par cron toutes les heures.
# Lit profiles.json, exécute les profils dont le planning est échu,
# effectue les snapshots et le prune selon la rétention.
#
# Log : /var/log/zbm-scheduled.log
# =============================================================================

from __future__ import annotations

import json
import hashlib
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

BOOT           = Path("/boot")
SNAPSHOTS_DIR  = BOOT / "snapshots"
PROFILES_FILE  = SNAPSHOTS_DIR / "profiles.json"
LOG_FILE       = Path("/var/log/zbm-scheduled.log")

# Abréviations composants → dataset ZFS
DATASET_TPLS = {
    "ovl": "fast_pool/overlay-{system}",
    # var/log/tmp supprimés : architecture overlay (fast_pool/overlay-{system} suffit)
}


def log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with LOG_FILE.open("a") as f:
            f.write(line + "\n")
    except Exception:
        pass


def run(cmd: list[str], timeout: int = 180) -> tuple[bool, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0, (r.stdout + r.stderr).strip()
    except Exception as e:
        return False, str(e)


def dataset_exists(ds: str) -> bool:
    ok, _ = run(["zfs", "list", ds])
    return ok


def human_size(n: float) -> str:
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} TB"


def dir_size(p: Path) -> str:
    try:
        total = sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
        return human_size(total)
    except Exception:
        return "?"


def md5file(p: Path) -> str:
    try:
        return hashlib.md5(p.read_bytes()).hexdigest()
    except Exception:
        return ""


def load_profiles() -> list[dict]:
    try:
        return json.loads(PROFILES_FILE.read_text())
    except Exception:
        return []


def save_profiles(profiles: list[dict]) -> None:
    tmp = PROFILES_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(profiles, indent=2))
    tmp.rename(PROFILES_FILE)


def is_due(profile: dict) -> bool:
    schedule = profile.get("schedule", "none")
    if schedule == "none":
        return False
    last_run = profile.get("last_run", "")
    if not last_run:
        return True
    try:
        last = datetime.fromisoformat(last_run)
    except Exception:
        return True
    delta_h = (datetime.now() - last).total_seconds() / 3600
    thresholds = {"daily": 24, "weekly": 168, "monthly": 720}
    return delta_h >= thresholds.get(schedule, 9999)


def snap_name(profile: dict, timestamp: str) -> str:
    system = profile.get("system", "sys")
    label  = (profile.get("rootfs_label") or system).replace(" ", "-").replace("/", "-")
    comps  = "+".join(profile.get("components", ["var"]))
    return f"{system}_{label}_{comps}_{timestamp}"


def get_dataset(comp: str, system: str) -> str | None:
    tpl = DATASET_TPLS.get(comp)
    return tpl.format(system=system) if tpl else None


def do_snapshot(profile: dict) -> bool:
    """Exécute un snapshot complet selon le profil. Retourne succès."""
    system     = profile.get("system", "")
    components = profile.get("components", [])
    timestamp  = datetime.now().strftime("%Y%m%d-%H%M%S")
    name       = snap_name(profile, timestamp)
    set_dir    = SNAPSHOTS_DIR / system / name

    log(f"  Création : {name}")
    set_dir.mkdir(parents=True, exist_ok=True)

    md5s: dict[str, str] = {}
    sizes: dict[str, str] = {}

    for comp in components:
        ds = get_dataset(comp, system)
        if not ds or not dataset_exists(ds):
            log(f"  ⚠️  Dataset absent : {ds} — ignoré")
            continue

        # Snapshot ZFS
        ok, msg = run(["zfs", "snapshot", f"{ds}@{name}"])
        if not ok:
            log(f"  ❌ zfs snapshot {ds} : {msg}")
            import shutil; shutil.rmtree(set_dir, ignore_errors=True)
            return False

        # Export zstd
        out_file = set_dir / f"{comp}.zst"
        try:
            zfs_p  = subprocess.Popen(
                ["zfs", "send", f"{ds}@{name}"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            zstd_p = subprocess.Popen(
                ["zstd", "-T0", "-3", "-q", "-o", str(out_file)],
                stdin=zfs_p.stdout, stderr=subprocess.PIPE
            )
            zfs_p.stdout.close()  # type: ignore
            _, err_b = zstd_p.communicate()
            zfs_rc   = zfs_p.wait()
            if zstd_p.returncode != 0 or zfs_rc != 0:
                log(f"  ❌ Export {comp} : {err_b.decode().strip()}")
                import shutil; shutil.rmtree(set_dir, ignore_errors=True)
                return False
            md5s[comp]  = md5file(out_file)
            sizes[comp] = human_size(out_file.stat().st_size)
            log(f"  ✅ [{comp}] {sizes[comp]}")
        except Exception as exc:
            log(f"  ❌ Exception {comp} : {exc}")
            import shutil; shutil.rmtree(set_dir, ignore_errors=True)
            return False

    if not md5s:
        import shutil; shutil.rmtree(set_dir, ignore_errors=True)
        return False

    # snap.meta
    meta_lines = [
        f"# snap.meta — cron {datetime.now().isoformat()}",
        f"snap_name={name}",
        f"system={system}",
        f"rootfs_label={profile.get('rootfs_label', '')}",
        f"components={'+'.join(components)}",
        f"timestamp={timestamp}",
        f"total_size={dir_size(set_dir)}",
        f"zfs_snap_name={name}",
        f"profile_id={profile.get('id', '')}",
        f"profile_name={profile.get('name', '')}",
        "archived=false",
        "",
    ]
    for comp, m in md5s.items():
        meta_lines.append(f"md5_{comp}={m}")
    tmp = set_dir / "snap.meta.tmp"
    tmp.write_text("\n".join(meta_lines) + "\n")
    tmp.rename(set_dir / "snap.meta")

    log(f"  Set créé : {name}")
    return True


def do_prune(profile: dict) -> None:
    """Supprime les sets excédentaires pour ce profil (archivés uniquement)."""
    system    = profile.get("system", "")
    keep      = profile.get("retention", 7)
    sys_dir   = SNAPSHOTS_DIR / system
    if not sys_dir.exists():
        return

    # Sets triés du plus récent au plus ancien
    sets = sorted(
        [d for d in sys_dir.iterdir() if d.is_dir()],
        reverse=True,
    )

    to_del = sets[keep:]
    for s in to_del:
        meta_file = s / "snap.meta"
        archived  = False
        snap_zfs  = ""
        if meta_file.exists():
            for line in meta_file.read_text().splitlines():
                if line.startswith("archived="):
                    archived = line.split("=", 1)[1].strip().lower() == "true"
                elif line.startswith("zfs_snap_name="):
                    snap_zfs = line.split("=", 1)[1].strip()

        if not archived:
            log(f"  ⚠️  {s.name} non archivé — ignoré dans prune")
            continue

        # Détruire snapshots ZFS
        comps = profile.get("components", [])
        if snap_zfs:
            for comp in comps:
                ds = get_dataset(comp, system)
                if ds:
                    run(["zfs", "destroy", f"{ds}@{snap_zfs}"])

        import shutil
        shutil.rmtree(s, ignore_errors=True)
        log(f"  🗑️  Supprimé : {s.name}")


# =============================================================================
# MAIN
# =============================================================================
if __name__ == "__main__":
    if os.geteuid() != 0:
        log("ERREUR : root requis")
        sys.exit(1)

    log("=== zbm-run-scheduled démarré ===")
    profiles = load_profiles()
    due      = [p for p in profiles if is_due(p)]

    if not due:
        log("Aucun profil échu — rien à faire")
        sys.exit(0)

    log(f"{len(due)} profil(s) échu(s)")
    updated = False

    for profile in due:
        name = profile.get("name", "?")
        log(f"--- Profil : {name} ---")
        success = do_snapshot(profile)
        if success:
            profile["last_run"] = datetime.now().isoformat()
            updated = True
            do_prune(profile)
        else:
            log(f"❌ Snapshot échoué pour : {name}")

    if updated:
        # Réécrire profiles.json avec les last_run mis à jour
        all_profiles = load_profiles()
        updated_ids  = {p["id"]: p for p in due if p.get("last_run")}
        for i, p in enumerate(all_profiles):
            if p.get("id") in updated_ids:
                all_profiles[i] = updated_ids[p["id"]]
        save_profiles(all_profiles)

    log("=== Fin ===")
PYEOF

chmod +x "$MOUNTPOINT/usr/local/bin/zbm-run-scheduled.py"
ok "zbm-run-scheduled.py"

# =============================================================================
# 2. CRONTAB
# =============================================================================
step "Installation du fichier cron"

cat > "$MOUNTPOINT/etc/cron.d/zbm-snapshots" << 'CRON'
# ZBM — Snapshots planifiés
# Le script lit profiles.json et décide lui-même si un profil est échu.
# Fréquence : toutes les heures (la granularité minimale d'un profil est daily).
0 * * * *   root   /usr/local/bin/zbm-run-scheduled.py

# Archivage mensuel automatique vers data_pool (1er du mois à 5h)
0 5 1 * *   root   /usr/local/bin/zbm-monthly-archive.sh
CRON
ok "/etc/cron.d/zbm-snapshots"

# =============================================================================
# 3. SCRIPT ARCHIVAGE MENSUEL
# =============================================================================
step "Création de zbm-monthly-archive.sh"

cat > "$MOUNTPOINT/usr/local/bin/zbm-monthly-archive.sh" << 'SH'
#!/bin/bash
# Archivage mensuel de tous les sets vers data_pool/archives
# Appelé par cron le 1er du mois.

LOG="/var/log/zbm-archive.log"
ts() { date '+%Y-%m-%d %H:%M:%S'; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }

log "=== Archivage mensuel ==="

if ! zpool list data_pool >/dev/null 2>&1; then
    log "ERREUR : data_pool non disponible"
    exit 1
fi

SNAP_BASE="/boot/snapshots"

for SYS_DIR in "$SNAP_BASE"/*/; do
    SYS=$(basename "$SYS_DIR")
    [[ "$SYS" == "profiles.json" ]] && continue   # pas un répertoire système
    ARC_DIR="/data_pool/archives/$SYS"
    mkdir -p "$ARC_DIR"

    for SET_DIR in "$SYS_DIR"*/; do
        [[ -d "$SET_DIR" ]] || continue
        SET=$(basename "$SET_DIR")
        DST="$ARC_DIR/$SET"

        if [[ -d "$DST" ]]; then
            log "  $SYS/$SET : déjà archivé"
            continue
        fi

        log "  Copie $SYS/$SET ..."
        rsync -a --checksum "$SET_DIR" "$ARC_DIR/" && {
            # Marquer comme archivé
            META="$SET_DIR/snap.meta"
            [[ -f "$META" ]] && sed -i 's/^archived=.*/archived=true/' "$META"
            log "  ✅ $SYS/$SET"
        } || log "  ❌ $SYS/$SET : rsync échoué"
    done
done

log "=== Fin archivage ==="
SH
chmod +x "$MOUNTPOINT/usr/local/bin/zbm-monthly-archive.sh"
ok "zbm-monthly-archive.sh"

# =============================================================================
# 4. LOGROTATE
# =============================================================================
step "Logrotate"

cat > "$MOUNTPOINT/etc/logrotate.d/zbm" << 'LR'
/var/log/zbm-scheduled.log
/var/log/zbm-archive.log
/var/log/zbm-stream.log
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
ok "logrotate zbm"

# =============================================================================
# 5. SERVICE OPENRC POUR L'INTERFACE PYTHON
# =============================================================================
step "Service OpenRC zbm-startup (réseau + stream + TUI)"

# Copier zbm-startup depuis le projet (service complet avec réseau DHCP, stream YouTube, TUI)
_STARTUP_SRC="${SCRIPT_DIR}/../system/zbm-startup"
if [[ -f "$_STARTUP_SRC" ]]; then
    install -m 0755 "$_STARTUP_SRC" "$MOUNTPOINT/etc/init.d/zbm-startup"
    ok "zbm-startup installé depuis system/zbm-startup"
else
    # Fallback : générer le service minimal si le fichier source est absent
    warn "system/zbm-startup introuvable — génération du service minimal"
    cat > "$MOUNTPOINT/etc/init.d/zbm-startup" << 'RC'
#!/sbin/openrc-run

description="ZBM Startup — Réseau, stream YouTube, interface Python"

depend() {
    need localmount
    after net zfs-mount
    before getty
    use logger
}

ZBM_LOG="/var/log/zbm-startup.log"
ZBM_CURRENT_SYS="/run/zbm-current-system"

start() {
    checkpath -f -m 0640 -o root:root "$ZBM_LOG"
    einfo "zbm-startup : démarrage"
    # Monter python.sfs
    local python_sfs
    python_sfs=$(ls /boot/images/startup/python-*.sfs 2>/dev/null | sort | tail -1 || true)
    if [[ -f "$python_sfs" ]]; then
        mkdir -p /mnt/python
        mountpoint -q /mnt/python || mount -t squashfs -o loop,ro "$python_sfs" /mnt/python
    fi
    # Lancer TUI sur TTY1
    local venv_python="/mnt/python/venv/bin/python3"
    local interface="/mnt/python/etc/zfsbootmenu/python_interface.py"
    [[ -f "$venv_python" && -f "$interface" ]] || { ewarn "python.sfs non disponible"; return 0; }
    openvt -c 1 -f -s -- env TERM=linux COLORTERM=truecolor         "$venv_python" "$interface" </dev/tty1 >/dev/tty1 2>/dev/tty1 &
    einfo "TUI lancée sur TTY1 (PID $!)"
}

stop() {
    einfo "zbm-startup : arrêt"
}
RC
    chmod +x "$MOUNTPOINT/etc/init.d/zbm-startup"
    ok "zbm-startup (service minimal fallback)"
fi

# Activer le service si rc-update est disponible
if command -v rc-update >/dev/null 2>&1; then
    rc-update add zbm-startup default 2>/dev/null         && ok "zbm-startup activé au démarrage"         || warn "rc-update : activation manuelle requise : rc-update add zbm-startup default"
fi

# =============================================================================
# RÉSUMÉ
# =============================================================================
echo ""
echo -e "${GREEN}${BOLD}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║         ✅ TÂCHES CRON INSTALLÉES                           ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo "  Scripts :"
echo "    zbm-run-scheduled.py    — snapshots planifiés (lit profiles.json)"
echo "    zbm-monthly-archive.sh  — archivage mensuel → data_pool"
echo ""
echo "  Cron :"
echo "    0 * * * *   zbm-run-scheduled.py   (vérif. toutes les heures)"
echo "    0 5 1 * *   zbm-monthly-archive.sh (1er du mois à 5h)"
echo ""
echo "  Les planifications sont gérées depuis l'UI Python :"
echo "    Snapshots → Profil → Planification"
echo ""
echo "  Logs :"
echo "    /var/log/zbm-scheduled.log"
echo "    /var/log/zbm-archive.log"
echo "    (rotation hebdo, 8 semaines)"
echo ""
