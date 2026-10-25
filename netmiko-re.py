import re
from netmiko import ConnectHandler

KEY_PATH = r"/home/kawaii/.ssh/cisco_rsa"

routers = [
    {"device_type": "cisco_ios", "ip": "172.31.25.4", "username": "admin", "use_keys": True, "key_file": KEY_PATH, "disabled_algorithms": {"pubkeys": ["rsa-sha2-512", "rsa-sha2-256"]},},
    {"device_type": "cisco_ios", "ip": "172.31.25.5", "username": "admin", "use_keys": True, "key_file": KEY_PATH, "disabled_algorithms": {"pubkeys": ["rsa-sha2-512", "rsa-sha2-256"]},}
]

for r in routers:
    with ConnectHandler(**r) as ssh:
        ver_out = ssh.send_command("show version")
        int_out = ssh.send_command("show ip interface brief")

        uptime = re.search(r"uptime is (.*)", ver_out)
        active_intfs = re.findall(r"^(\S+)\s+[\d\.]+\s+YES\s+\S+\s+up\s+up", int_out, re.MULTILINE)

        print(f"\nDevice {r['ip']}:")
        print(f"  Uptime: {uptime.group(1) if uptime else 'Unknown'}")
        print(f"  Active Interfaces: {', '.join(active_intfs)}")

