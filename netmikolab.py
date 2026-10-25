from netmiko import ConnectHandler

KEY_FILE = r"/home/kawaii/.ssh/cisco_rsa"

CLOUD_NETWORK = "10.42.0.0"
CLOUD_WILDCARD = "0.0.255.255"
MGMT_NETWORK = "172.31.25.0"
MGMT_WILDCARD = "0.0.0.15"

BASE = {
    "device_type": "cisco_ios",
    "username": "admin",
    "use_keys": True,
    "key_file": KEY_FILE,
    "disabled_algorithms": {"pubkeys": ["rsa-sha2-512", "rsa-sha2-256"]},
}

S1 = {**BASE, "host": "172.31.25.3"}
R1 = {**BASE, "host": "172.31.25.4"}
R2 = {**BASE, "host": "172.31.25.5"}


def push(device, commands, label):
    print(f"--- Configuring {label} ---")
    conn = ConnectHandler(**device)
    conn.enable()
    output = conn.send_config_set(commands)
    print(output)
    conn.save_config()
    conn.disconnect()
    print(f"{label}: done\n")


def configure_s1():
    commands = [
        "vlan 101",
        "name CONTROL-DATA",
        "exit",
        # Port to R2
        "int g0/1",
        "switchport mode access",
        "switchport access vlan 101",
        "exit",
        # Port to UbuntuServer-2
        "int g1/1",
        "switchport mode access",
        "switchport access vlan 101",
        "exit",
        # Restrict telnet/ssh
        "ip access-list standard MGMT_ACCESS",
        f"permit {MGMT_NETWORK} {MGMT_WILDCARD}",
        f"permit {CLOUD_NETWORK} {CLOUD_WILDCARD}",
        "deny any log",
        "exit",
        "line vty 0 4",
        "access-class MGMT_ACCESS in",
        "exit",
    ]
    push(S1, commands, "S1-P")


def configure_r1():
    commands = [
        "int Lo0",
        "ip vrf forwarding control-data",
        "ip address 10.140.100.1 255.255.255.255",
        "exit",
        "router ospf 1 vrf control-data",
        "router-id 10.140.100.1",
        "network 10.140.1.0 0.0.0.255 area 0",
        "network 10.140.12.0 0.0.0.3 area 0",
        "network 10.140.100.1 0.0.0.0 area 0",
        "exit",
        "ip access-list standard MGMT_ACCESS",
        f"permit {MGMT_NETWORK} {MGMT_WILDCARD}",
        f"permit {CLOUD_NETWORK} {CLOUD_WILDCARD}",
        "deny any log",
        "exit",
        "line vty 0 4",
        "access-class MGMT_ACCESS in",
        "exit",
    ]
    push(R1, commands, "R1-P")


def configure_r2():
    commands = [
        "int Lo0",
        "ip vrf forwarding control-data",
        "ip address 10.140.100.2 255.255.255.255",
        "exit",
        "router ospf 1 vrf control-data",
        "router-id 10.140.100.2",
        "network 10.140.2.0 0.0.0.255 area 0",
        "network 10.140.12.0 0.0.0.3 area 0",
        "network 10.140.100.2 0.0.0.0 area 0",
        "default-information originate",
        "exit",
        # Default route to NAT cloud
        "ip route vrf control-data 0.0.0.0 0.0.0.0 g0/3",
        # PAT / NAT overload
        "ip access-list standard NAT_ACL",
        "permit 10.140.0.0 0.0.255.255",
        "exit",
        "int g0/1",
        "ip nat inside",
        "exit",
        "int g0/2",
        "ip nat inside",
        "exit",
        "int g0/3",
        "ip nat outside",
        "exit",
        "no ip nat inside source list 1 interface GigabitEthernet0/3 overload",
        "ip nat inside source list NAT_ACL interface GigabitEthernet0/3 vrf control-data overload",
        # Restrict telnet/ssh
        "ip access-list standard MGMT_ACCESS",
        f"permit {MGMT_NETWORK} {MGMT_WILDCARD}",
        f"permit {CLOUD_NETWORK} {CLOUD_WILDCARD}",
        "deny any log",
        "exit",
        "line vty 0 4",
        "access-class MGMT_ACCESS in",
        "exit",
    ]
    push(R2, commands, "R2-P")


if __name__ == "__main__":
    configure_s1()
    configure_r1()
    configure_r2()
