"""Read-only startup hints; never configure host forwarding or firewall rules."""

from __future__ import annotations

import ipaddress
import json
import os
import platform
import shutil
import socket
import subprocess


def _ipv4(value: str) -> bool:
    try:
        address = ipaddress.IPv4Address(value)
        return not (address.is_loopback or address.is_unspecified or address.is_link_local)
    except (ValueError, TypeError):
        return False


def _local_addresses() -> list[str]:
    try:
        result = subprocess.run(["ip", "-j", "-4", "address", "show", "scope", "global"],
                                capture_output=True, text=True, timeout=2, check=True)
        return sorted({entry["local"] for interface in json.loads(result.stdout)
                       for entry in interface.get("addr_info", []) if _ipv4(entry.get("local"))})
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError):
        # Route lookup only: UDP connect sends no packet and needs no internet service.
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as route:
                route.connect(("192.0.2.1", 9))
                address = route.getsockname()[0]
                return [address] if _ipv4(address) else []
        except OSError:
            return []


def _windows_network(port: int) -> dict:
    powershell = shutil.which("powershell.exe")
    if powershell is None:
        raise OSError("Windows PowerShell is unavailable")
    # All commands are queries. The sole interpolated value is a validated integer.
    script = """
$ErrorActionPreference = 'Stop'
$addresses = @([Net.NetworkInformation.NetworkInterface]::GetAllNetworkInterfaces() |
    Where-Object { $_.OperationalStatus -eq 'Up' } | ForEach-Object {
        $properties = $_.GetIPProperties()
        if (@($properties.GatewayAddresses | Where-Object {
            $_.Address.AddressFamily -eq 'InterNetwork' -and $_.Address.ToString() -ne '0.0.0.0'
        }).Count -gt 0) {
            $properties.UnicastAddresses | Where-Object { $_.Address.AddressFamily -eq 'InterNetwork' } |
                ForEach-Object { $_.Address.ToString() }
        }
    })
$listeners = @([Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners() |
    Where-Object { $_.Port -eq PORT_NUMBER } | ForEach-Object { $_.Address.ToString() })
@{addresses=$addresses; listeners=$listeners; forwarding=@(netsh interface portproxy show v4tov4)} |
    ConvertTo-Json -Compress
""".replace("PORT_NUMBER", str(int(port)))
    result = subprocess.run([powershell, "-NoProfile", "-NonInteractive", "-Command", script],
                            capture_output=True, text=True, timeout=8, check=True)
    data = json.loads(result.stdout.lstrip("\ufeff"))
    if not isinstance(data, dict):
        raise ValueError("Invalid Windows network response")
    return data


def startup_urls(host: str, port: int) -> list[str]:
    """Report useful URLs, keeping bind and verified reachability distinct."""
    if host in {"127.0.0.1", "localhost"}:
        return [f"Open http://{host}:{port}/app/creation.html",
                "Local access only. For trusted-LAN access restart with --host 0.0.0.0."]

    addresses = _local_addresses() if host == "0.0.0.0" else ([host] if _ipv4(host) else [])
    lines = [f"Listening on {host}:{port}",
             "Trusted LAN only: this server has no authentication. Do not expose it to the internet."]
    wsl = bool(os.environ.get("WSL_DISTRO_NAME")) or "microsoft" in platform.release().lower()
    if wsl:
        try:
            windows = _windows_network(port)
            for address in windows.get("addresses", []):
                if not _ipv4(address):
                    continue
                lines.append(f"LAN URL: http://{address}:{port}/app/creation.html")
                forwarded = any(
                    len(fields := row.split()) == 4 and fields[0] in {address, "0.0.0.0"}
                    and fields[1] == str(port) and fields[2] in addresses and fields[3] == str(port)
                    for row in windows.get("forwarding", [])
                )
                listening = any(value in windows.get("listeners", []) for value in (address, "0.0.0.0"))
                if forwarded and listening:
                    lines.append("  Windows forwarding/listener detected; firewall and phone access are not verified.")
                else:
                    lines.append("  No matching Windows forwarding/listener detected. WSL NAT needs authorised setup; "
                                 "mirrored mode uses its own firewall policy.")
            if not windows.get("addresses"):
                lines.append("Windows LAN address not found; phone access is not verified.")
        except (OSError, subprocess.SubprocessError, ValueError, TypeError, AttributeError):
            lines.append("Windows LAN check unavailable; inspect WSL forwarding/firewall before phone access.")
        lines.extend(f"WSL address (not necessarily reachable from LAN): http://{address}:{port}/app/creation.html"
                     for address in addresses)
    else:
        lines.extend(f"LAN URL: http://{address}:{port}/app/creation.html" for address in addresses)
        lines.append("Firewall and access from another device are not verified.")
    if not addresses:
        lines.append("No usable IPv4 address found; inspect the host network configuration.")
    return lines
