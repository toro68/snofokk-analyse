import socket
import subprocess
from datetime import datetime


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

# Test nettverkstilkobling
server_ip = "192.168.68.116"

# Test ping først
try:
    log(f"\nTester ping mot {server_ip}...")
    result = subprocess.run(['ping', '-c', '3', server_ip],
                          capture_output=True, text=True)
    if result.returncode == 0:
        log("✓ Server svarer på ping")
        print(result.stdout)
    else:
        log("✗ Server svarer ikke på ping")
except Exception as e:
    log(f"Feil ved ping: {e}")

# Test kritiske porter
ports = [
    80,    # Web
    445,   # SMB
    55000  # WHS
]

for port in ports:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        log(f"\nTester port {port}...")
        result = sock.connect_ex((server_ip, port))
        if result == 0:
            log(f"✓ Port {port} er ÅPEN")
        else:
            log(f"✗ Port {port} er LUKKET (error: {result})")
        sock.close()
    except Exception as e:
        log(f"Feil ved testing av port {port}: {e}")
        continue
