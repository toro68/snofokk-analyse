import subprocess
import time
import socket
import sys
from datetime import datetime


def log_event(message, level="INFO"):
    """Logger hendelser med tidsstempel og nivå"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {level}: {message}")


def debug_network_info(ip):
    """Samler detaljert nettverksinformasjon"""
    try:
        # Ping test
        log_event(f"Utfører ping test mot {ip}...", "DEBUG")
        ping_result = subprocess.run(
            ['ping', '-c', '1', '-W', '1', ip],
            capture_output=True,
            text=True
        )
        log_event(f"Ping resultat: {ping_result.returncode}", "DEBUG")
        
        # Traceroute
        log_event(f"Utfører traceroute mot {ip}...", "DEBUG")
        trace_result = subprocess.run(
            ['traceroute', '-w', '1', '-q', '1', ip],
            capture_output=True,
            text=True
        )
        if trace_result.stdout:
            log_event(f"Traceroute resultat:\n{trace_result.stdout}", "DEBUG")
            
    except Exception as e:
        log_event(f"Feil ved nettverksdiagnostikk: {str(e)}", "ERROR")


def get_whs_info(ip):
    """Sjekk Windows Home Server spesifikk informasjon"""
    try:
        # Test NetBIOS navn med timeout
        log_event("Sjekker NetBIOS navn...", "DEBUG")
        result = subprocess.run(
            ['nmblookup', '-A', '-T', '1', ip],
            capture_output=True,
            text=True
        )
        if result.stdout:
            log_event(f"NetBIOS svar:\n{result.stdout}")
            
        # Test Windows shares med kort timeout
        log_event("Sjekker Windows shares...", "DEBUG")
        result = subprocess.run(
            ['smbclient', '-L', ip, '-N', '-t', '1'],
            capture_output=True,
            text=True
        )
        if result.stdout:
            log_event(f"SMB shares funnet:\n{result.stdout}")
            
    except Exception as e:
        log_event(f"Feil ved WHS info: {str(e)}", "ERROR")


def check_port(ip, port, service_name=""):
    """Test TCP porter med banner grabbing"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        
        log_event(f"Tester port {port} ({service_name})...", "DEBUG")
        result = sock.connect_ex((ip, port))
        
        if result == 0:
            log_event(f"Port {port} ({service_name}) er nå ÅPEN!", "SUCCESS")
            try:
                if port == 445:  # SMB
                    sock.send(b"\x00\x00\x00\x85\xff\x53\x4d\x42")
                elif port == 3389:  # RDP
                    sock.send(b"\x03\x00\x00\x13")
                elif port in [80, 8080]:  # HTTP
                    sock.send(b"GET / HTTP/1.0\r\n\r\n")
                    
                try:
                    banner = sock.recv(1024)
                    log_event(f"Banner fra {service_name}: {banner}", "DEBUG")
                except socket.timeout:
                    log_event(f"Timeout ved banner grab fra {service_name}", "DEBUG")
                    
            except Exception as e:
                log_event(f"Feil ved banner grab på {service_name}: {str(e)}", "ERROR")
                
        else:
            log_event(f"Port {port} er lukket (error: {result})", "DEBUG")
                
        sock.close()
        return result == 0
        
    except socket.error as e:
        log_event(f"Nettverksfeil på {service_name}: {str(e)}", "ERROR")
        return False


def scan_network():
    """Skanner nettverket for mulige servere"""
    potential_ips = [
        "192.168.68.102",
        "192.168.68.105",
        "192.168.68.109",
        "192.168.68.110",
        "192.168.68.111",
        "192.168.68.112",
        "192.168.68.113",
        "192.168.68.116"
    ]
    
    log_event("Skanner nettverket for HP MediaSmart Server...")
    for ip in potential_ips:
        try:
            # Test basic connectivity
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            if sock.connect_ex((ip, 55000)) == 0:
                log_event(f"Fant mulig server på {ip}!", "SUCCESS")
                return ip
            sock.close()
        except socket.error:
            continue
    return None


def main():
    # Finn server først
    target_server = scan_network()
    if not target_server:
        target_server = "192.168.68.170"  # Fallback til standard IP
    
    # Windows Home Server porter med beskrivelser
    whs_ports = [
        (80, "HTTP Web Admin"),
        (139, "NetBIOS Session"),
        (445, "SMB File Sharing"),
        (3389, "Remote Desktop"),
        (4125, "WHS Remote Access"),
        (5357, "Web Services"),
        (8080, "WHS Web Interface"),
        (8443, "WHS HTTPS Interface"),
        (55000, "WHS Remote Streaming"),
        (56000, "WHS Remote Access"),
    ]
    
    log_event("Starter overvåkning av HP MediaSmart Server EX490 reset")
    log_event(f"Target IP: {target_server}")
    log_event("Venter på at serveren skal komme online...")
    
    # Hold oversikt over porter som har vært åpne
    ports_seen_open = set()
    
    while True:
        # Kjør nettverksdiagnostikk
        debug_network_info(target_server)
        
        # Test basic connectivity først
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            if sock.connect_ex((target_server, 7)) == 0:
                log_event("Server er online!", "SUCCESS")
            sock.close()
        except socket.error as e:
            log_event(f"Venter på nettverkstilkobling... ({str(e)})", "WAIT")
            time.sleep(5)
            continue
        
        # Sjekk Windows-tjenester
        log_event("\nSjekker Windows Home Server tjenester...")
        get_whs_info(target_server)
        
        # Test porter og logg endringer
        for port, service in whs_ports:
            is_open = check_port(target_server, port, service)
            
            # Logg når en port først blir åpen
            if is_open and port not in ports_seen_open:
                log_event(f"NY TJENESTE OPPDAGET: {service} på port {port}", "SUCCESS")
                ports_seen_open.add(port)
            # Logg hvis en tidligere åpen port blir lukket
            elif not is_open and port in ports_seen_open:
                log_event(f"TJENESTE FORSVANT: {service} på port {port}", "WARNING")
                ports_seen_open.remove(port)
        
        log_event("\nVenter 5 sekunder før neste sjekk...", "INFO")
        time.sleep(5)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nOvervåkning avsluttet av bruker")
        sys.exit(0) 