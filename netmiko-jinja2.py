import os
from jinja2 import Environment, FileSystemLoader, ChoiceLoader, DictLoader
from netmiko import ConnectHandler

KEY_FILE = r"/home/kawaii/.ssh/cisco_rsa"
TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")

# Network definitions
CLOUD_NETWORK = "10.42.0.0"
CLOUD_WILDCARD = "0.0.255.255"
MGMT_NETWORK = "172.31.25.0"
MGMT_WILDCARD = "0.0.0.15"

COMMON_DATA = {
    "cloud_network": CLOUD_NETWORK,
    "cloud_wildcard": CLOUD_WILDCARD,
    "mgmt_network": MGMT_NETWORK,
    "mgmt_wildcard": MGMT_WILDCARD,
}

BASE = {
    "device_type": "cisco_ios",
    "username": "admin",
    "use_keys": True,
    "key_file": KEY_FILE,
    "disabled_algorithms": {"pubkeys": ["rsa-sha2-512", "rsa-sha2-256"]},
}

S1_DEVICE = {**BASE, "host": "172.31.25.3"}
R1_DEVICE = {**BASE, "host": "172.31.25.4"}
R2_DEVICE = {**BASE, "host": "172.31.25.5"}

# Inline templates as fallback if templates directory is absent
FALLBACK_TEMPLATES = {
    "mgmt_access.j2": """
ip access-list standard MGMT_ACCESS
 permit {{ mgmt_network }} {{ mgmt_wildcard }}
 permit {{ cloud_network }} {{ cloud_wildcard }}
 deny any log
 exit
line vty 0 4
 access-class MGMT_ACCESS in
 exit
""".strip(),
    "switch.j2": """
{% for vlan in vlans %}
vlan {{ vlan.id }}
 name {{ vlan.name }}
 exit
{% endfor %}
{% for port in access_ports %}
int {{ port.interface }}
 switchport mode access
 switchport access vlan {{ port.vlan }}
 exit
{% endfor %}
{% include 'mgmt_access.j2' %}
""".strip(),
    "router.j2": """
{% for lb in loopbacks %}
int {{ lb.interface }}
{% if lb.vrf %}
 ip vrf forwarding {{ lb.vrf }}
{% endif %}
 ip address {{ lb.ip }} {{ lb.mask }}
 exit
{% endfor %}
{% if ospf %}
router ospf {{ ospf.process_id }}{% if ospf.vrf %} vrf {{ ospf.vrf }}{% endif %}
 router-id {{ ospf.router_id }}
{% for net in ospf.networks %}
 network {{ net.network }} {{ net.wildcard }} area {{ net.area }}
{% endfor %}
{% if ospf.default_information_originate %}
 default-information originate
{% endif %}
 exit
{% endif %}
{% if static_routes %}
{% for r in static_routes %}
ip route{% if r.vrf %} vrf {{ r.vrf }}{% endif %} {{ r.prefix }} {{ r.mask }} {{ r.interface }}
{% endfor %}
{% endif %}
{% if nat %}
ip access-list standard {{ nat.acl_name }}
 permit {{ nat.permit_network }} {{ nat.permit_wildcard }}
 exit
{% for intf in nat.inside_interfaces %}
int {{ intf }}
 ip nat inside
 exit
{% endfor %}
{% for intf in nat.outside_interfaces %}
int {{ intf }}
 ip nat outside
 exit
{% endfor %}
no ip nat inside source list 1 interface {{ nat.outside_interface }} overload
ip nat inside source list {{ nat.acl_name }} interface {{ nat.outside_interface }} vrf {{ nat.vrf }} overload
{% endif %}
{% include 'mgmt_access.j2' %}
""".strip(),
}


def get_jinja_env():
    """Build Jinja2 Environment with file system loader and fallback."""
    loaders = []
    if os.path.isdir(TEMPLATES_DIR):
        loaders.append(FileSystemLoader(TEMPLATES_DIR))
    loaders.append(DictLoader(FALLBACK_TEMPLATES))
    return Environment(loader=ChoiceLoader(loaders), trim_blocks=True, lstrip_blocks=True)


def render_commands(env, template_name, data):
    """Render a Jinja2 template and return list of configuration commands."""
    template = env.get_template(template_name)
    rendered = template.render(**data)
    commands = [line.strip() for line in rendered.splitlines() if line.strip() and not line.strip().startswith("!")]
    return commands


def push(device, commands, label):
    """Deploy configuration commands to a network device via Netmiko."""
    print(f"--- Configuring {label} ---")
    conn = ConnectHandler(**device)
    conn.enable()
    output = conn.send_config_set(commands)
    print(output)
    conn.save_config()
    conn.disconnect()
    print(f"{label}: done\n")


def configure_s1(env=None):
    if env is None:
        env = get_jinja_env()
    s1_data = {
        **COMMON_DATA,
        "vlans": [
            {"id": 101, "name": "CONTROL-DATA"},
        ],
        "access_ports": [
            {"interface": "g0/1", "vlan": 101},
            {"interface": "g1/1", "vlan": 101},
        ],
    }
    commands = render_commands(env, "switch.j2", s1_data)
    push(S1_DEVICE, commands, "S1-P")


def configure_r1(env=None):
    if env is None:
        env = get_jinja_env()
    r1_data = {
        **COMMON_DATA,
        "loopbacks": [
            {"interface": "Lo0", "vrf": "control-data", "ip": "10.140.100.1", "mask": "255.255.255.255"},
        ],
        "ospf": {
            "process_id": 1,
            "vrf": "control-data",
            "router_id": "10.140.100.1",
            "networks": [
                {"network": "10.140.1.0", "wildcard": "0.0.0.255", "area": 0},
                {"network": "10.140.12.0", "wildcard": "0.0.0.3", "area": 0},
                {"network": "10.140.100.1", "wildcard": "0.0.0.0", "area": 0},
            ],
            "default_information_originate": False,
        },
    }
    commands = render_commands(env, "router.j2", r1_data)
    push(R1_DEVICE, commands, "R1-P")


def configure_r2(env=None):
    if env is None:
        env = get_jinja_env()
    r2_data = {
        **COMMON_DATA,
        "loopbacks": [
            {"interface": "Lo0", "vrf": "control-data", "ip": "10.140.100.2", "mask": "255.255.255.255"},
        ],
        "ospf": {
            "process_id": 1,
            "vrf": "control-data",
            "router_id": "10.140.100.2",
            "networks": [
                {"network": "10.140.2.0", "wildcard": "0.0.0.255", "area": 0},
                {"network": "10.140.12.0", "wildcard": "0.0.0.3", "area": 0},
                {"network": "10.140.100.2", "wildcard": "0.0.0.0", "area": 0},
            ],
            "default_information_originate": True,
        },
        "static_routes": [
            {"vrf": "control-data", "prefix": "0.0.0.0", "mask": "0.0.0.0", "interface": "g0/3"},
        ],
        "nat": {
            "acl_name": "NAT_ACL",
            "permit_network": "10.140.0.0",
            "permit_wildcard": "0.0.255.255",
            "inside_interfaces": ["g0/1", "g0/2"],
            "outside_interfaces": ["g0/3"],
            "outside_interface": "GigabitEthernet0/3",
            "vrf": "control-data",
        },
    }
    commands = render_commands(env, "router.j2", r2_data)
    push(R2_DEVICE, commands, "R2-P")


if __name__ == "__main__":
    env = get_jinja_env()
    configure_s1(env)
    configure_r1(env)
    configure_r2(env)
