"""
fsdeploy.function.boot.init
=============================
Génération du script init pour l'initramfs.

Types d'init :
  - zbm     : lance ZFSBootMenu standard
  - minimal : monte ZFS + pivot_root, pas de ZBM
  - stream  : réseau + Python + YouTube stream, sans rootfs
  - custom  : script init fourni par l'utilisateur
"""

import os
import stat
from pathlib import Path
from typing import Any

from scheduler.model.task import Task
from scheduler.model.resource import Resource, INITRAMFS
from scheduler.model.lock import Lock
from scheduler.security.decorator import security


# ─── Templates ────────────────────────────────────────────────────────────────

INIT_HEADER = """\
#!/bin/sh
# fsdeploy init — generated, do not edit
# Type: {init_type}

set -e
export PATH="/usr/sbin:/usr/bin:/sbin:/bin"

# Mount virtual filesystems
mount -t proc  proc  /proc
mount -t sysfs sysfs /sys
mount -t devtmpfs devtmpfs /dev
mkdir -p /dev/pts /run
mount -t devpts devpts /dev/pts
mount -t tmpfs  tmpfs  /run

# Parse cmdline
cmdline=$(cat /proc/cmdline)
"""

INIT_ZFS_IMPORT = """\
# Import ZFS pools
modprobe zfs 2>/dev/null || true
sleep 1

# Import boot_pool
zpool import -f -N -o cachefile=none {boot_pool} 2>/dev/null || true

# Mount boot dataset
mkdir -p /mnt/boot
mount -t zfs {boot_dataset} /mnt/boot || true
"""

INIT_NETWORK = """\
# Network setup
for iface in /sys/class/net/e*; do
    iface_name=$(basename "$iface")
    ip link set "$iface_name" up
    # DHCP via udhcpc or dhclient
    if command -v udhcpc >/dev/null 2>&1; then
        udhcpc -i "$iface_name" -s /usr/share/udhcpc/default.script -q -n &
    elif command -v dhclient >/dev/null 2>&1; then
        dhclient -1 "$iface_name" &
    fi
done
sleep 3
"""

INIT_OVERLAY = """\
# Overlay mount : squashfs lower + ZFS upper
mkdir -p /mnt/lower /mnt/upper /mnt/work /mnt/merged

# Mount rootfs squashfs
mount -t squashfs -o loop,ro {rootfs_sfs} /mnt/lower

# Mount overlay upper (ZFS dataset)
zpool import -f -N -o cachefile=none {overlay_pool} 2>/dev/null || true
mount -t zfs {overlay_dataset} /mnt/upper
mkdir -p /mnt/upper/upper /mnt/upper/work

# Assemble overlayfs
mount -t overlay overlay \\
    -o lowerdir=/mnt/lower,upperdir=/mnt/upper/upper,workdir=/mnt/upper/work \\
    /mnt/merged
"""

INIT_PIVOT = """\
# Pivot root
cd /mnt/merged
mkdir -p .old_root
pivot_root . .old_root

# Clean up old root
exec chroot . /bin/sh -c '
    mount -t proc  proc  /proc
    mount -t sysfs sysfs /sys
    mount -t devtmpfs devtmpfs /dev
    umount -l /.old_root 2>/dev/null || true
    rmdir /.old_root 2>/dev/null || true
    exec /sbin/init
'
"""

INIT_STREAM = """\
# Stream mode — no rootfs, Python + YouTube
mkdir -p /tmp /var/log

# Wait for network
for i in $(seq 1 30); do
    if ip route | grep -q default; then
        break
    fi
    sleep 1
done

# Extract Python environment
if [ -f /mnt/boot/images/python.sfs ]; then
    mkdir -p /opt/python
    mount -t squashfs -o loop,ro /mnt/boot/images/python.sfs /opt/python
    export PATH="/opt/python/bin:$PATH"
    export PYTHONPATH="/opt/python/lib/python3/site-packages"
fi

# Launch fsdeploy in stream mode
exec python3 -m fsdeploy --mode stream {stream_args}
"""

INIT_ZBM = """\
# Launch ZFSBootMenu
if [ -x /libexec/zfsbootmenu-init ]; then
    exec /libexec/zfsbootmenu-init
fi

# Fallback : direct boot
echo "ZFSBootMenu not found, attempting direct boot..."
{fallback}
"""


@security.boot.init
class BootInitTask(Task):
    """
    Génère le script /init pour l'initramfs.
    """

    def required_resources(self):
        return [INITRAMFS]

    def required_locks(self):
        return [Lock("initramfs", owner_id=str(self.id))]

    def run(self) -> dict[str, Any]:
        init_type = self.params.get("init_type", "zbm")
        output_path = Path(self.params.get("output", "/tmp/fsdeploy-init"))

        # Construire le script
        sections = [INIT_HEADER.format(init_type=init_type)]

        # ZFS import (commun à tous sauf custom)
        if init_type != "custom":
            boot_pool = self.params.get("boot_pool", "boot_pool")
            boot_dataset = self.params.get("boot_dataset", f"{boot_pool}/boot")
            sections.append(INIT_ZFS_IMPORT.format(
                boot_pool=boot_pool,
                boot_dataset=boot_dataset,
            ))

        # Sections spécifiques
        if init_type == "zbm":
            sections.append(INIT_ZBM.format(
                fallback="exec /bin/sh"
            ))

        elif init_type == "minimal":
            overlay_pool = self.params.get("overlay_pool", "fast_pool")
            overlay_dataset = self.params.get("overlay_dataset", f"{overlay_pool}/overlay-system")
            rootfs_sfs = self.params.get("rootfs_sfs", "/mnt/boot/images/rootfs.sfs")
            sections.append(INIT_OVERLAY.format(
                rootfs_sfs=rootfs_sfs,
                overlay_pool=overlay_pool,
                overlay_dataset=overlay_dataset,
            ))
            sections.append(INIT_PIVOT)

        elif init_type == "stream":
            sections.append(INIT_NETWORK)
            stream_key = self.params.get("stream_key", "")
            stream_args = f"--stream-key {stream_key}" if stream_key else ""
            sections.append(INIT_STREAM.format(stream_args=stream_args))

        elif init_type == "custom":
            custom_path = self.params.get("init_file", "")
            if custom_path and Path(custom_path).is_file():
                sections = [Path(custom_path).read_text()]
            else:
                raise FileNotFoundError(f"Custom init file not found: {custom_path}")

        # Écrire
        script = "\n".join(sections)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(script)
        output_path.chmod(stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)

        return {
            "init_type": init_type,
            "output": str(output_path),
            "size": len(script),
        }
