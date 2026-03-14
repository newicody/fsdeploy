#!/bin/sh
### BEGIN INIT INFO
# Provides:          zbm-startup
# Required-Start:    $local_fs $remote_fs $network $syslog
# Required-Stop:     $local_fs $remote_fs
# Default-Start:     2 3 4 5
# Default-Stop:      0 1 6
# Short-Description: ZBM Startup — Réseau, stream YouTube, interface Python
# Description:       Démarre le réseau DHCP, monte python.sfs,
#                    lance le stream YouTube et la TUI Textual sur TTY1.
### END INIT INFO

PATH=/sbin:/usr/sbin:/bin:/usr/bin
NAME=zbm-startup
ZBM_CURRENT_SYS=/run/zbm-current-system
ZBM_STREAM_PID=/run/zbm-stream.pid
ZBM_TUI_PID=/run/zbm-tui.pid
ZBM_LOG=/var/log/zbm-startup.log

[ -f /lib/lsb/init-functions ] && . /lib/lsb/init-functions || {
    log_daemon_msg() { printf "%s: %s\n" "$1" "$2"; }
    log_end_msg()    { [ "$1" -eq 0 ] && echo "OK" || echo "FAIL"; }
    log_warning_msg(){ printf "WARN: %s\n" "$1"; }
}

_log() { echo "[$(date '+%H:%M:%S')] $*" >> "$ZBM_LOG"; }

# =============================================================================
# LECTURE PRESET
# =============================================================================
_read_preset() {
    local KEY="$1"
    local SYS="${2:-$(cat "$ZBM_CURRENT_SYS" 2>/dev/null || echo "systeme1")}"
    local PRESET="/boot/presets/${SYS}.json"
    [ -f "$PRESET" ] || return 1
    python3 -c "
import json
try:
    d = json.load(open('$PRESET'))
    print(d.get('$KEY', '') or '')
except Exception:
    pass
" 2>/dev/null
}

# =============================================================================
# RÉSEAU DHCP
# =============================================================================
_start_network() {
    _log "Réseau : démarrage DHCP"
    IFACE=""

    IFACE_CFG=$(_read_preset "network_iface")
    if [ -n "$IFACE_CFG" ] && [ "$IFACE_CFG" != "auto" ]; then
        IFACE="$IFACE_CFG"
    fi

    if [ -z "$IFACE" ]; then
        for iface_drv in /sys/class/net/*/device/driver; do
            [ -e "$iface_drv" ] || continue
            DRV=$(basename "$(readlink -f "$iface_drv")")
            if [ "$DRV" = "e1000e" ]; then
                IFACE=$(basename "$(dirname "$(dirname "$iface_drv")")")
                break
            fi
        done
    fi

    if [ -z "$IFACE" ]; then
        IFACE=$(ls /sys/class/net/ 2>/dev/null | grep -v "^lo$" | head -1 || true)
    fi

    if [ -z "$IFACE" ]; then
        _log "WARN: aucune interface réseau trouvée"
        return 1
    fi

    _log "Interface : $IFACE"
    ip link set "$IFACE" up >> "$ZBM_LOG" 2>&1 || true

    if command -v dhclient >/dev/null 2>&1; then
        dhclient "$IFACE" >> "$ZBM_LOG" 2>&1 &
    elif command -v udhcpc >/dev/null 2>&1; then
        udhcpc -i "$IFACE" -b >> "$ZBM_LOG" 2>&1 &
    else
        _log "WARN: dhclient/udhcpc introuvable"
    fi
}

# =============================================================================
# MONTAGE python.sfs
# =============================================================================
_mount_python() {
    PYTHON_SFS=$(ls /boot/images/startup/python-*.sfs 2>/dev/null | sort | tail -1 || true)
    [ -n "$PYTHON_SFS" ] || { _log "WARN: python.sfs introuvable"; return 1; }
    mkdir -p /mnt/python
    if ! mountpoint -q /mnt/python; then
        mount -t squashfs -o loop,ro "$PYTHON_SFS" /mnt/python >> "$ZBM_LOG" 2>&1
        _log "python.sfs monté : $(basename "$PYTHON_SFS")"
    fi
}

# =============================================================================
# STREAM YOUTUBE
# =============================================================================
_start_stream() {
    STREAM_KEY=$(_read_preset "stream_key")
    [ -n "$STREAM_KEY" ] || return 0

    DELAY=$(_read_preset "stream_delay")
    DELAY="${DELAY:-30}"

    _log "Stream YouTube dans ${DELAY}s"

    (
        sleep "$DELAY"
        ffmpeg -y \
            -f fbdev   -framerate 30 -i /dev/fb0 \
            -f alsa    -i hw:0,0 \
            -c:v libx264 -preset veryfast -tune zerolatency \
            -b:v 4500k -maxrate 4500k -bufsize 9000k \
            -pix_fmt yuv420p -g 60 -keyint_min 60 \
            -c:a aac -b:a 128k -ar 44100 \
            -f flv "rtmp://a.rtmp.youtube.com/live2/$STREAM_KEY" \
            >> "$ZBM_LOG" 2>&1
    ) &
    echo $! > "$ZBM_STREAM_PID"
}

# =============================================================================
# TUI TEXTUAL
# =============================================================================
_start_tui() {
    VENV_PY="/mnt/python/venv/bin/python3"
    INTERFACE="/mnt/python/etc/zfsbootmenu/python_interface.py"

    if [ ! -f "$VENV_PY" ] || [ ! -f "$INTERFACE" ]; then
        _log "WARN: python.sfs non disponible — TUI non lancée"
        return 1
    fi

    openvt -c 1 -f -s -- env TERM=linux COLORTERM=truecolor \
        "$VENV_PY" "$INTERFACE" </dev/tty1 >/dev/tty1 2>/dev/tty1 &
    echo $! > "$ZBM_TUI_PID"
    _log "TUI lancée sur TTY1 (PID $(cat "$ZBM_TUI_PID"))"
}

# =============================================================================
# POINTS D'ENTRÉE
# =============================================================================
do_start() {
    log_daemon_msg "Starting $NAME"
    mkdir -p "$(dirname "$ZBM_LOG")"
    touch "$ZBM_LOG"
    _start_network
    _mount_python
    _start_stream
    _start_tui
    log_end_msg 0
}

do_stop() {
    log_daemon_msg "Stopping $NAME"
    [ -f "$ZBM_STREAM_PID" ] && kill "$(cat "$ZBM_STREAM_PID")" 2>/dev/null && rm -f "$ZBM_STREAM_PID" || true
    [ -f "$ZBM_TUI_PID" ]    && kill "$(cat "$ZBM_TUI_PID")"    2>/dev/null && rm -f "$ZBM_TUI_PID"    || true
    mountpoint -q /mnt/python 2>/dev/null && umount /mnt/python 2>/dev/null || true
    log_end_msg 0
}

do_status() {
    if [ -f "$ZBM_TUI_PID" ] && kill -0 "$(cat "$ZBM_TUI_PID")" 2>/dev/null; then
        echo "$NAME est actif (TUI PID $(cat "$ZBM_TUI_PID"))"
        return 0
    fi
    echo "$NAME est arrêté"
    return 1
}

case "$1" in
    start)                do_start  ;;
    stop)                 do_stop   ;;
    restart|force-reload) do_stop; sleep 1; do_start ;;
    status)               do_status ;;
    *)
        echo "Usage: $0 {start|stop|restart|force-reload|status}" >&2
        exit 3
        ;;
esac
