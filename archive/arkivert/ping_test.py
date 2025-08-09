import subprocess
from datetime import datetime

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def ping_ip(ip):
    try:
        result = subprocess.run(['ping', '-c', '1', '-W', '1', ip], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            log(f"✓ {ip} svarer på ping")
            return True
        else:
            log(f"✗ {ip} svarer ikke")
        return False
    except Exception as e:
        log(f"Feil ved ping av {ip}: {e}")
        return False

# Test alle IP-er i rekkefølge
for i in range(1, 20):  # Start med de første 20 IP-ene
    ip = f"192.168.68.{i}"
    ping_ip(ip) 