import socket
import sys
from datetime import datetime
import subprocess


def log(msg, level="INFO"):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {level}: {msg}")


def ping_test(ip):
    """Test om IP er aktiv med ping"""
    try:
        result = subprocess.run(['ping', '-c', '1', '-W', '1', ip], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            log(f"Ping vellykket til {ip}", "SUCCESS")
            return True
        return False
    except Exception as e:
        log(f"Ping feilet til {ip}: {str(e)}", "ERROR")
        return False


def check_port(ip, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.5)  # Redusert timeout
    try:
        log(f"Tester {ip}:{port}", "DEBUG")
        result = sock.connect_ex((ip, port))
        if result == 0:
            log(f"Port {port} er åpen på {ip}", "SUCCESS")
            # Prøv å hente banner
            try:
                if port == 80:
                    sock.send(b"GET / HTTP/1.0\r\n\r\n")
                    data = sock.recv(1024)
                    log(f"Banner fra {ip}:{port}: {data}", "DEBUG")
            except:
                pass
        else:
            log(f"Port {port} er lukket på {ip} (error: {result})", "DEBUG")
        return result == 0
    except Exception as e:
        log(f"Feil ved testing av {ip}:{port} - {str(e)}", "ERROR")
        return False
    finally:
        sock.close()


def main():
    log("Starter debugging av nettverkstilkobling...")
    
    # Test spesifikke IP-adresser først
    test_ips = [
        "192.168.68.1",   # Router
        "192.168.68.102", # Mulig server
        "192.168.68.105", 
        "192.168.68.109",
        "192.168.68.110",
        "192.168.68.111"
    ]
    
    log("Tester tilkobling til kjente IP-adresser...")
    for ip in test_ips:
        if ping_test(ip):
            # Test relevante porter
            for port in [80, 445, 55000]:
                check_port(ip, port)
        else:
            log(f"Ingen respons fra {ip}", "WARNING")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nDebugging avbrutt av bruker")
        sys.exit(0) 