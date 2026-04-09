"""
Tâches de détection de partitions par pattern.
"""

import glob
import subprocess
import json
from pathlib import Path

from fsdeploy.lib.scheduler.model.task import Task
from fsdeploy.lib.scheduler.model.intent import Intent
from fsdeploy.lib.scheduler.core.registry import register_intent

class PartitionDetectTask(Task):
    """Scanner les partitions correspondant à un pattern."""

    def run(self):
        pattern = self.context.get("pattern", "/dev/sd*")
        fstype = self.context.get("fstype")
        devices = glob.glob(pattern)
        partitions = []
        for dev in devices:
            # Obtenir info via blkid
            info = self.get_blkid(dev)
            size = self.get_size(dev)
            partitions.append({
                "device": dev,
                "type": info.get("TYPE", "unknown"),
                "size": size,
                "mountpoint": self.get_mountpoint(dev),
                "squashfs": self.has_squashfs(dev),
            })
        return {"partitions": partitions}

    def get_blkid(self, dev):
        try:
            out = subprocess.check_output(["blkid", "-o", "json", dev], text=True)
            data = json.loads(out)
            if isinstance(data, list) and data:
                return data[0]
        except:
            pass
        return {}

    def get_size(self, dev):
        try:
            out = subprocess.check_output(["blockdev", "--getsize64", dev], text=True).strip()
            return out
        except:
            return "unknown"

    def get_mountpoint(self, dev):
        try:
            out = subprocess.check_output(["findmnt", "-n", "-o", "TARGET", dev], text=True).strip()
            return out
        except:
            return ""

    def has_squashfs(self, dev):
        # Détecter si le device contient un système de fichiers squashfs
        # en lisant la signature magique (sqsh / hsqs)
        try:
            with open(dev, 'rb') as f:
                magic = f.read(4)
                # signatures squashfs possibles (little‑endian)
                if magic in (b'hsqs', b'sqsh', b'qshs', b'shsq'):
                    return True
        except:
            pass
        return False

@register_intent("partition.detect")
class PartitionDetectIntent(Intent):
    def build_tasks(self):
        return [PartitionDetectTask()]


class MountSquashfsTask(Task):
    """Monte une partition squashfs et extrait les modules."""

    def run(self):
        device = self.context.get("device")
        # Simulation: monter avec mount
        import tempfile
        import subprocess
        mountpoint = tempfile.mkdtemp(prefix="squashfs_")
        try:
            subprocess.run(["mount", "-t", "squashfs", device, mountpoint], check=True)
            # Extraire les modules (simulation)
            import os
            modules = []
            for root, dirs, files in os.walk(mountpoint):
                for f in files:
                    if f.endswith('.ko'):
                        modules.append(os.path.join(root, f))
            subprocess.run(["umount", mountpoint], check=True)
            os.rmdir(mountpoint)
            return {"success": True, "modules": modules}
        except Exception as e:
            return {"success": False, "error": str(e)}

@register_intent("partition.squashfs.mount")
class MountSquashfsIntent(Intent):
    def build_tasks(self):
        return [MountSquashfsTask()]
