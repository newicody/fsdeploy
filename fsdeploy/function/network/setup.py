"""
fsdeploy.function.network.setup
================================
Configuration réseau pour l'initramfs et le système.

Modes :
  - dhcp : configuration automatique via DHCP
  - static : configuration manuelle (IP, gateway, DNS)

Utilisé pour :
  - Boot réseau sans rootfs
  - Stream YouTube depuis l'initramfs
  - Téléchargement de squashfs distants
"""

import os
import socket
import subprocess
import time
from pathlib import Path
from typing import Any, Optional

from scheduler.model.task import Task
from scheduler.model.resource import Resource, NETWORK
from scheduler.model.lock import Lock
from scheduler.security.decorator import security


def _find_first_interface() -> Optional[str]:
    """Trouve la première interface réseau non-loopback."""
    net_dir = Path("/sys/class/net")
    for iface in net_dir.iterdir():
        name = iface.name
        if name == "lo":
            continue
        # Préférer les interfaces Ethernet
        if name.startswith(("eth", "en", "ens", "enp")):
            return name
    # Fallback : première interface non-lo
    for iface in net_dir.iterdir():
        if iface.name != "lo":
            return iface.name
    return None


def _check_connectivity(host: str = "8.8.8.8", port: int = 53, timeout: int = 3) -> bool:
    """Vérifie la connectivité réseau."""
    try:
        socket.setdefaulttimeout(timeout)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, port))
        sock.close()
        return True
    except (socket.error, OSError):
        return False


def _get_interface_ip(interface: str) -> Optional[str]:
    """Récupère l'adresse IP d'une interface."""
    try:
        import fcntl
        import struct
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        ip = socket.inet_ntoa(fcntl.ioctl(
            sock.fileno(),
            0x8915,  # SIOCGIFADDR
            struct.pack('256s', interface[:15].encode('utf-8'))
        )[20:24])
        return ip
    except Exception:
        return None


@security.network.setup
class NetworkSetupTask(Task):
    """
    Configure le réseau.
    
    Params:
      - interface: interface à configurer (auto-détection si vide)
      - method: "dhcp" ou "static"
      - timeout: timeout DHCP en secondes
      - ip_address: pour method=static
      - gateway: pour method=static
      - dns: pour method=static (liste ou string)
    """

    def required_resources(self):
        return [NETWORK]

    def required_locks(self):
        iface = self.params.get("interface", "")
        if iface:
            return [Lock(f"network.{iface}", owner_id=str(self.id))]
        return [Lock("network", owner_id=str(self.id))]

    def run(self) -> dict[str, Any]:
        interface = self.params.get("interface", "")
        method = self.params.get("method", "dhcp")
        timeout = self.params.get("timeout", 30)

        # Auto-détection de l'interface
        if not interface:
            interface = _find_first_interface()
            if not interface:
                raise RuntimeError("No network interface found")

        results = {
            "interface": interface,
            "method": method,
            "configured": False,
            "connected": False,
            "ip_address": None,
        }

        # Vérifier si déjà connecté
        if _check_connectivity():
            results["connected"] = True
            results["ip_address"] = _get_interface_ip(interface)
            results["configured"] = True
            results["already_configured"] = True
            return results

        # Activer l'interface
        self.run_cmd(f"ip link set {interface} up", sudo=True, check=False)

        if method == "dhcp":
            results.update(self._configure_dhcp(interface, timeout))
        elif method == "static":
            results.update(self._configure_static(interface))
        else:
            raise ValueError(f"Unknown method: {method}")

        # Vérifier la connectivité
        results["connected"] = _check_connectivity()
        results["ip_address"] = _get_interface_ip(interface)

        return results

    def _configure_dhcp(self, interface: str, timeout: int) -> dict:
        """Configure via DHCP."""
        # Essayer plusieurs clients DHCP
        dhcp_clients = [
            ("dhclient", f"dhclient -1 -timeout {timeout} {interface}"),
            ("udhcpc", f"udhcpc -i {interface} -n -q -t {timeout // 5}"),
            ("dhcpcd", f"dhcpcd -w -t {timeout} {interface}"),
        ]

        for client_name, cmd in dhcp_clients:
            # Vérifier si le client existe
            r = self.run_cmd(f"command -v {client_name}", check=False)
            if not r.success:
                continue

            # Lancer le client DHCP
            r = self.run_cmd(cmd, sudo=True, check=False, timeout=timeout + 10)
            if r.success or _check_connectivity():
                return {
                    "configured": True,
                    "dhcp_client": client_name,
                }

        # Fallback : attente passive
        deadline = time.time() + timeout
        while time.time() < deadline:
            if _check_connectivity():
                return {"configured": True, "dhcp_client": "passive"}
            time.sleep(2)

        return {"configured": False, "error": "DHCP timeout"}

    def _configure_static(self, interface: str) -> dict:
        """Configure avec IP statique."""
        ip_address = self.params.get("ip_address", "")
        gateway = self.params.get("gateway", "")
        dns = self.params.get("dns", "")

        if not ip_address:
            raise ValueError("ip_address required for static configuration")

        # Ajouter l'IP
        # Format attendu : "192.168.1.100/24" ou "192.168.1.100"
        if "/" not in ip_address:
            ip_address = f"{ip_address}/24"

        self.run_cmd(f"ip addr add {ip_address} dev {interface}", sudo=True)

        # Ajouter la route par défaut
        if gateway:
            self.run_cmd(
                f"ip route add default via {gateway} dev {interface}",
                sudo=True,
                check=False,
            )

        # Configurer DNS
        if dns:
            dns_servers = dns if isinstance(dns, list) else [dns]
            resolv_content = "\n".join(f"nameserver {s}" for s in dns_servers)
            Path("/etc/resolv.conf").write_text(resolv_content + "\n")

        return {"configured": True}


@security.network.status
class NetworkStatusTask(Task):
    """Vérifie l'état du réseau."""

    def run(self) -> dict[str, Any]:
        interface = self.params.get("interface", "") or _find_first_interface()

        results = {
            "interface": interface,
            "link_up": False,
            "ip_address": None,
            "gateway": None,
            "dns": [],
            "connected": False,
        }

        if not interface:
            return results

        # État du lien
        r = self.run_cmd(f"ip link show {interface}", check=False)
        results["link_up"] = "UP" in r.stdout if r.success else False

        # Adresse IP
        results["ip_address"] = _get_interface_ip(interface)

        # Gateway
        r = self.run_cmd("ip route show default", check=False)
        if r.success and "via" in r.stdout:
            parts = r.stdout.split()
            try:
                via_idx = parts.index("via")
                results["gateway"] = parts[via_idx + 1]
            except (ValueError, IndexError):
                pass

        # DNS
        resolv = Path("/etc/resolv.conf")
        if resolv.exists():
            for line in resolv.read_text().splitlines():
                if line.startswith("nameserver"):
                    parts = line.split()
                    if len(parts) >= 2:
                        results["dns"].append(parts[1])

        # Connectivité
        results["connected"] = _check_connectivity()

        return results


@security.network.wait
class NetworkWaitTask(Task):
    """Attend que le réseau soit disponible."""

    def run(self) -> dict[str, Any]:
        timeout = self.params.get("timeout", 60)
        check_interval = self.params.get("interval", 2)
        host = self.params.get("host", "8.8.8.8")

        deadline = time.time() + timeout
        attempts = 0

        while time.time() < deadline:
            attempts += 1
            if _check_connectivity(host=host):
                return {
                    "connected": True,
                    "attempts": attempts,
                    "elapsed": timeout - (deadline - time.time()),
                }
            time.sleep(check_interval)

        return {
            "connected": False,
            "attempts": attempts,
            "timeout": True,
        }


# Re-exports
__all__ = ["NetworkSetupTask", "NetworkStatusTask", "NetworkWaitTask"]
