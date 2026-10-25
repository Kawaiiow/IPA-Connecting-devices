"""Interface/Topology Configuration and Validation using TextFSM and Netmiko.

Configures interface descriptions on R1, R2, and S1 based on CDP neighbors
and network topology specifications.
"""

import re
from netmiko import ConnectHandler

KEY_FILE = r"/home/kawaii/.ssh/cisco_rsa"

BASE = {
    "device_type": "cisco_ios",
    "username": "admin",
    "use_keys": True,
    "key_file": KEY_FILE,
    "disabled_algorithms": {"pubkeys": ["rsa-sha2-512", "rsa-sha2-256"]},
}

DEVICES = {
    "R1": {**BASE, "host": "172.31.25.4"},
    "R2": {**BASE, "host": "172.31.25.5"},
    "S1": {**BASE, "host": "172.31.25.3"},
}


def shorten_interface(intf_str: str) -> str:
    """Shorten interface names (e.g. GigabitEthernet0/1 -> G0/1)."""
    if not intf_str:
        return ""
    intf = intf_str.strip()
    m = re.match(r"^(?:GigabitEthernet|Gigabit|Gig|Gi)\s*(.*)$", intf, re.IGNORECASE)
    if m:
        return f"G{m.group(1)}"
    m = re.match(r"^(?:FastEthernet|FastEth|Fa|F)\s*(.*)$", intf, re.IGNORECASE)
    if m:
        return f"Fa{m.group(1)}"
    m = re.match(r"^(?:Ethernet|Eth|Et)\s*(.*)$", intf, re.IGNORECASE)
    if m:
        return f"Et{m.group(1)}"
    m = re.match(r"^(?:Loopback|Lo)\s*(.*)$", intf, re.IGNORECASE)
    if m:
        return f"Lo{m.group(1)}"
    m = re.match(r"^(?:Vlan|Vl)\s*(.*)$", intf, re.IGNORECASE)
    if m:
        return f"Vl{m.group(1)}"
    return intf


def normalize_interface(intf_str: str) -> str:
    """Normalize interface name to standard IOS abbreviation (e.g. Gi0/1, Gi1/1)."""
    short = shorten_interface(intf_str)
    if short.startswith("G") and not short.startswith("Gi"):
        return f"Gi{short[1:]}"
    return short


def clean_device_name(dev_name: str) -> str:
    """Strip domain name from hostname (e.g. R2.ipa.com -> R2)."""
    if not dev_name:
        return ""
    return dev_name.strip().split(".")[0]


def format_cdp_description(remote_interface: str, remote_device: str) -> str:
    """Format description for link to remote Cisco device.

    Example: Connect to G0/1 of R2
    """
    short_intf = shorten_interface(remote_interface)
    clean_dev = clean_device_name(remote_device)
    return f"Connect to {short_intf} of {clean_dev}"


def get_cdp_neighbors(conn) -> list:
    """Retrieve CDP neighbors using TextFSM."""
    try:
        parsed = conn.send_command("show cdp neighbors detail", use_textfsm=True)
        if isinstance(parsed, list) and parsed:
            return parsed
    except Exception:
        pass

    # Fallback to standard show cdp neighbors
    parsed = conn.send_command("show cdp neighbors", use_textfsm=True)
    if isinstance(parsed, list):
        return parsed
    return []


def get_interface_descriptions(conn) -> dict:
    """Retrieve current interface descriptions using TextFSM."""
    parsed = conn.send_command("show interfaces description", use_textfsm=True)
    result = {}
    if isinstance(parsed, list):
        for entry in parsed:
            port = normalize_interface(entry.get("port", ""))
            desc = entry.get("description", "")
            if port:
                result[port] = desc
    return result


def generate_descriptions(device_name: str, cdp_neighbors: list) -> dict:
    """Generate expected interface descriptions based on CDP neighbors and topology."""
    descriptions = {}

    # Map discovered Cisco CDP neighbors
    cdp_map = {}
    for entry in cdp_neighbors:
        loc_intf = normalize_interface(entry.get("local_interface", ""))
        rem_dev = entry.get("neighbor_name", "")
        # Handle ntc_templates where neighbor_interface may be split
        rem_intf = entry.get("neighbor_interface", "")
        if not rem_intf or rem_intf.isdigit():
            platform_val = entry.get("platform", "")
            if platform_val:
                rem_intf = f"{platform_val} {rem_intf}".strip()
        if loc_intf:
            cdp_map[loc_intf] = format_cdp_description(rem_intf, rem_dev)

    if device_name == "R1":
        # Control/Data plane interfaces are Gi0/1 and Gi0/2
        # One connects to R2 (found via CDP), the other connects to PC
        r2_intf = None
        for intf, desc in cdp_map.items():
            if "of R2" in desc:
                descriptions[intf] = desc
                r2_intf = intf
            elif intf == "Gi0/0":
                # Management connection to S0
                descriptions[intf] = desc

        # PC interface is the other control/data interface
        pc_intf = "Gi0/2" if r2_intf == "Gi0/1" else "Gi0/1"
        descriptions[pc_intf] = "Connect to PC"

    elif device_name == "R2":
        # Control/Data plane: Gi0/1 (to R1), Gi0/2 (to S1), Gi0/3 (to WAN)
        for intf, desc in cdp_map.items():
            if "of R1" in desc or "of S1" in desc or intf == "Gi0/0":
                descriptions[intf] = desc

        # Fallback if CDP neighbors temporarily not visible
        if "Gi0/1" not in descriptions:
            descriptions["Gi0/1"] = "Connect to G0/1 of R1"
        if "Gi0/2" not in descriptions:
            descriptions["Gi0/2"] = "Connect to G0/1 of S1"

        # WAN interface
        descriptions["Gi0/3"] = "Connect to WAN"

    elif device_name == "S1":
        # Control/Data plane: Gi0/1 (to R2), Gi1/1 (to PC)
        for intf, desc in cdp_map.items():
            if "of R2" in desc or intf == "Gi0/0":
                descriptions[intf] = desc

        # Fallback for R2 if needed
        if "Gi0/1" not in descriptions:
            descriptions["Gi0/1"] = "Connect to G0/2 of R2"

        # PC connection
        descriptions["Gi1/1"] = "Connect to PC"

    return descriptions


def apply_descriptions(conn, descriptions: dict) -> list:
    """Send description configuration commands to device via Netmiko."""
    commands = []
    for intf, desc in descriptions.items():
        commands.extend([
            f"interface {intf}",
            f"description {desc}",
            "exit",
        ])
    if commands:
        conn.send_config_set(commands)
        conn.save_config()
    return commands


def configure_device(device_name: str, device_dict: dict) -> dict:
    """Connect to a device, discover neighbors, and configure interface descriptions."""
    print(f"--- Configuring interface descriptions on {device_name} ---")
    conn = ConnectHandler(**device_dict)
    conn.enable()

    cdp_neighbors = get_cdp_neighbors(conn)
    descriptions = generate_descriptions(device_name, cdp_neighbors)

    print(f"Applying descriptions on {device_name}:")
    for intf, desc in descriptions.items():
        print(f"  {intf} -> {desc}")

    apply_descriptions(conn, descriptions)
    conn.disconnect()
    print(f"{device_name}: done\n")
    return descriptions


def main():
    """Main execution entry point to configure R1, R2, and S1."""
    results = {}
    for name, params in DEVICES.items():
        results[name] = configure_device(name, params)
    return results


if __name__ == "__main__":
    main()
