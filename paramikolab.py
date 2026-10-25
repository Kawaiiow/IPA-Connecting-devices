import paramiko

devices = [
    "172.31.25.1",
    "172.31.25.2",
    "172.31.25.3",
    "172.31.25.4",
    "172.31.25.5"
]
key = paramiko.RSAKey.from_private_key_file("/home/kawaii/.ssh/cisco_rsa")

for ip in devices:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(hostname=ip, username="admin", pkey=key, look_for_keys=False)
        stdin, stdout, stderr = client.exec_command("sh ip int b")
        print(stdout.read().decode())
    finally:
        client.close()

