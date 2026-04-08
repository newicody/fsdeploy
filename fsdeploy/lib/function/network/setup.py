"""
fsdeploy.function.network.setup
================================
Configuration réseau pour les trois contextes (live/initramfs/booted).

Détecte les interfaces, configure DHCP, vérifie la connectivité.
"""

import time
from pathlib import Path
from typing import Any

from scheduler.model.task import Task
from scheduler.model.resource import Resource, NETWORK
from scheduler.model.lock import Lock
from scheduler.security.decorator import security


@security.network.setup
class NetworkSetupTask(Task):
    """Configure le réseau."""

    def required_resources(self):
        return [NETWORK]

    def required_locks(self):
        return [Lock("network", owner_id=str(self.id))]

    def run(self) -> dict[str, Any]:
        timeout = self.params.get("timeout", 30)
        interface = self.params.get("interface", "")

        results = {
            "interfaces": [],
            "configured": [],
            "ip_address": "",
            "gateway": "",
            "connected": False,
        }

        # Détecter les interfaces
        results["interfaces"] = self._list_interfaces()

        if not results["interfaces"]:
            return results

        # Configurer
        targets = [interface] if interface else results["interfaces"]
        for iface in targets:
            if self._configure_interface(iface):
                results["configured"].append(iface)

        # Attendre une IP
        results["connected"] = self._wait_connectivity(timeout)

        if results["connected"]:
            results["ip_address"] = self._get_ip()
            results["gateway"] = self._get_gateway()

        return results

    def _list_interfaces(self) -> list[str]:
        """Liste les interfaces réseau physiques."""
        interfaces = []
        net_dir = Path("/sys/class/net")
        if not net_dir.exists():
            return interfaces
        for iface in net_dir.iterdir():
            name = iface.name
            if name == "lo":
                continue
            # Filtrer les interfaces virtuelles
            if (iface / "device").exists() or name.startswith(("eth", "en", "wl")):
                interfaces.append(name)
        return sorted(interfaces)

    def _configure_interface(self, iface: str) -> bool:
        """Active l'interface et lance DHCP."""
        # Activer
        self.run_cmd(f"ip link set {iface} up", sudo=True, check=False)

        # DHCP
        dhcp_tools = [
            f"udhcpc -i {iface} -s /usr/share/udhcpc/default.script -q -n -t 5",
            f"dhclient -1 -timeout 10 {iface}",
            f"dhcpcd -t 10 {iface}",
        ]

        for cmd in dhcp_tools:
            tool = cmd.split()[0]
            which = self.run_cmd(f"which {tool}", check=False)
            if which.success:
                result = self.run_cmd(cmd, sudo=True, check=False, timeout=15)
                if result.success:
                    return True
        return False

    def _wait_connectivity(self, timeout: int) -> bool:
        """Attend qu'une route par défaut soit présente."""
        start = time.monotonic()
        while time.monotonic() - start < timeout:
            result = self.run_cmd("ip route show default", check=False)
            if result.success and "default" in result.stdout:
                return True
            time.sleep(1)
        return False

    def _get_ip(self) -> str:
        """Retourne l'IP de la première interface configurée."""
        result = self.run_cmd(
            "ip -4 addr show scope global | grep inet | head -1",
            check=False,
        )
        if result.success and result.stdout.strip():
            parts = result.stdout.strip().split()
            for i, p in enumerate(parts):
                if p == "inet" and i + 1 < len(parts):
                    return parts[i + 1].split("/")[0]
        return ""

    def _get_gateway(self) -> str:
        result = self.run_cmd("ip route show default", check=False)
        if result.success:
            parts = result.stdout.strip().split()
            if "via" in parts:
                idx = parts.index("via")
                if idx + 1 < len(parts):
                    return parts[idx + 1]
        return ""
