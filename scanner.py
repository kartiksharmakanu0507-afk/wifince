"""
scanner.py — WiFi/LAN scanner using Windows ARP table.
Runs 'arp -a' and parses all active MAC addresses.
"""
import subprocess
import re


def scan_network():
    """
    Run 'arp -a' and return a set of all active MAC addresses on the LAN.
    MACs are normalized to lowercase colon-separated format: 'aa:bb:cc:dd:ee:ff'
    Works on Windows 10/11.
    """
    try:
        result = subprocess.run(
            ["arp", "-a"],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=0x08000000  # CREATE_NO_WINDOW on Windows
        )
        return _parse_macs(result.stdout)
    except Exception as e:
        print(f"[SCANNER] Error running arp -a: {e}")
        return set()


def get_mac_for_ip(ip):
    """
    Look up the MAC address for a specific IP using the ARP table.
    Returns a normalized MAC string or None.
    """
    if not ip or ip in ("127.0.0.1", "::1", "localhost"):
        return None
    try:
        result = subprocess.run(
            ["arp", "-a", ip],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=0x08000000
        )
        macs = _extract_macs(result.stdout)
        return macs[0] if macs else None
    except Exception as e:
        print(f"[SCANNER] Error getting MAC for {ip}: {e}")
        return None


def _parse_macs(arp_output):
    """Parse all MAC addresses from arp -a output and return as a set."""
    return set(_extract_macs(arp_output))


def _extract_macs(text):
    """
    Extract and normalize all MAC addresses from text.
    Windows uses dashes: 00-1A-2B-3C-4D-5E → normalized to 00:1a:2b:3c:4d:5e
    """
    pattern = r'[0-9a-fA-F]{2}(?:[:\-][0-9a-fA-F]{2}){5}'
    raw_macs = re.findall(pattern, text)
    return [mac.lower().replace('-', ':') for mac in raw_macs]
