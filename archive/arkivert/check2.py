import socket
import subprocess
import sys
from datetime import datetime


def log_event(message, level="INFO", debug=True):
    """Logger hendelser med tidsstempel og nivå"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if debug or level != "DEBUG":
        print(f"[{timestamp}] {level}: {message}")


def test_port(ip, port, timeout=1, send_data=False):
    """Test spesifikk port med detaljert output"""
    try:
        log_event(f"Tester port {port}...", "DEBUG")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)

        # Prøv å koble til
        start_time = datetime.now()
        result = sock.connect_ex((ip, port))
        connect_time = (datetime.now() - start_time).total_seconds()

        # Analyser resultatet
        if result == 0:
            msg = f"Port {port} er ÅPEN (tilkoblingstid: {connect_time:.3f}s)"
            log_event(msg, "SUCCESS")
        else:
            error_type = "Connection refused" if result == 61 else f"Error {result}"
            msg = f"Port {port}: LUKKET - {error_type} ({connect_time:.3f}s)"
            log_event(msg, "DEBUG")

        if result == 0 and send_data:
            try:
                if port == 445:  # SMB
                    log_event("Sender SMB negotiate...", "DEBUG")
                    sock.send(b"\x00\x00\x00\x2f\xff\x53\x4d\x42\x72\x00")
                elif port == 139:  # NetBIOS
                    log_event("Sender NetBIOS session request...", "DEBUG")
                    sock.send(b"\x81\x00\x00\x44\x20")
                elif port in [80, 8080]:  # HTTP
                    log_event("Sender HTTP GET...", "DEBUG")
                    sock.send(b"GET / HTTP/1.0\r\n\r\n")

                try:
                    data = sock.recv(1024)
                    log_event(f"Mottatt {len(data)} bytes", "DEBUG")
                    log_event(f"Data: {data}", "DEBUG")
                except TimeoutError:
                    log_event("Timeout ved lesing av data", "WARNING")
            except Exception as e:
                log_event(f"Feil ved datautveksling: {str(e)}", "ERROR")

        sock.close()
        return result == 0

    except socket.gaierror:
        log_event(f"Kunne ikke løse hostname for port {port}", "ERROR")
        return False
    except TimeoutError:
        log_event(f"Timeout ved tilkobling til port {port}", "WARNING")
        return False
    except Exception as e:
        log_event(f"Uventet feil på port {port}: {str(e)}", "ERROR")
        return False


def analyze_network_path(ip):
    """Analyserer nettverksstien til serveren"""
    log_event(f"=== Nettverksanalyse for {ip} ===", "DEBUG")

    try:
        # Sjekk om IP er i samme subnet
        local_ip = "192.168.68.101"  # Fra ARP output
        log_event(f"Lokal IP: {local_ip}", "DEBUG")
        log_event(f"Målserver IP: {ip}", "DEBUG")
        log_event("Merk: Server er i annet subnet (192.168.1.x)", "WARNING")

        # Test gateway tilkobling med mer detaljer
        gateway = "192.168.68.1"  # Fra route output
        log_event(f"Tester gateway {gateway}...", "DEBUG")
        gateway_cmd = ['ping', '-c', '1', '-W', '1', gateway]
        gateway_result = subprocess.run(
            gateway_cmd,
            capture_output=True,
            text=True
        )
        if gateway_result.returncode == 0:
            log_event("Gateway er tilgjengelig", "SUCCESS")
            # Sjekk gateway ARP
            gateway_arp = subprocess.run(
                ['arp', '-n', gateway],
                capture_output=True,
                text=True
            )
            log_event(f"Gateway MAC: {gateway_arp.stdout.strip()}", "DEBUG")
        else:
            log_event("Problemer med gateway tilkobling!", "ERROR")

        # Sjekk ruting
        log_event("Sjekker ruting til server...", "DEBUG")
        route_cmd = ['netstat', '-rn']
        route_result = subprocess.run(route_cmd, capture_output=True, text=True)
        routes = route_result.stdout.split('\n')
        for route in routes:
            if '192.168.1' in route or '192.168.68' in route:
                log_event(f"Relevant rute: {route}", "DEBUG")

        # Sjekk MAC-adresse med mer detaljer
        log_event("Sjekker MAC-adresse...", "DEBUG")
        mac_cmd = ['arp', '-n', ip]
        mac_result = subprocess.run(mac_cmd, capture_output=True, text=True)
        if "no entry" in mac_result.stdout:
            log_event("Ingen MAC-oppføring funnet - prøver å pinge først", "DEBUG")
            # Prøv å pinge med forskjellige pakke størrelser
            for size in [64, 1024, 1472]:  # Standard, Medium, Max
                ping_cmd = ['ping', '-c', '1', '-s', str(size), ip]
                ping_result = subprocess.run(ping_cmd, capture_output=True)
                status = "OK" if ping_result.returncode == 0 else "Feilet"
                log_event(f"Ping med {size} bytes: {status}", "DEBUG")

            # Sjekk ARP igjen
            mac_result = subprocess.run(mac_cmd, capture_output=True, text=True)
            log_event(f"ARP etter ping: {mac_result.stdout}", "DEBUG")

        # Test traceroute med flere detaljer
        log_event("Kjører detaljert traceroute...", "DEBUG")
        # Prøv både ICMP og UDP
        for proto in ['-I', '-U']:
            trace_cmd = ['traceroute', proto, '-w', '1', ip]
            trace_result = subprocess.run(
                trace_cmd,
                capture_output=True,
                text=True
            )
            proto_name = "ICMP" if proto == '-I' else "UDP"
            log_event(f"Traceroute ({proto_name}):\n{trace_result.stdout}", "DEBUG")

    except Exception as e:
        log_event(f"Feil ved nettverksanalyse: {str(e)}", "ERROR")


def debug_network_info(ip):
    """Samler detaljert nettverksinformasjon"""
    log_event(f"=== Starter nettverksdiagnostikk for {ip} ===", "DEBUG")

    # Analyser nettverkssti først
    analyze_network_path(ip)

    # Test viktige porter med data
    important_ports = [
        (80, "HTTP"),
        (139, "NetBIOS"),
        (445, "SMB"),
        (3389, "RDP"),
        (8080, "HTTP-Alt"),
        (8443, "HTTPS-Alt")
    ]

    log_event("Tester viktige porter med protokolldata...", "INFO")
    for port, service in important_ports:
        if test_port(ip, port, timeout=2, send_data=True):
            log_event(f"{service} port {port} er ÅPEN", "SUCCESS")

    # Detaljert ping analyse
    try:
        log_event("Utfører detaljert ping test...", "DEBUG")
        ping_cmd = ['ping', '-c', '3', '-W', '3', '-v', ip]
        log_event(f"Kjører: {' '.join(ping_cmd)}", "DEBUG")

        ping_result = subprocess.run(ping_cmd, capture_output=True, text=True)

        if ping_result.returncode == 0:
            log_event("Ping suksess!", "SUCCESS")
            # Analyser ping statistikk
            for line in ping_result.stdout.splitlines():
                if any(x in line.lower() for x in ['bytes from', 'statistics', 'round-trip']):
                    log_event(f"Ping detalj: {line}", "DEBUG")
        else:
            log_event("Ping feilet", "WARNING")

        if ping_result.stderr:
            log_event(f"Ping feil: {ping_result.stderr}", "WARNING")

    except Exception as e:
        log_event(f"Feil ved ping test: {str(e)}", "ERROR")

    # Test SMB tilkobling med forskjellige opsjoner
    try:
        log_event("Tester SMB tilkobling med forskjellige opsjoner...", "DEBUG")

        # Test 1: Anonym tilkobling
        smb_cmd1 = ['smbclient', '-L', f'//{ip}', '-N', '-d', '3']
        log_event("Test 1: Anonym tilkobling", "DEBUG")
        result1 = subprocess.run(smb_cmd1, capture_output=True, text=True)
        log_event(f"Resultat 1: {result1.stderr}", "DEBUG")

        # Test 2: Prøv med guest bruker
        smb_cmd2 = ['smbclient', '-L', f'//{ip}', '-U', 'guest%', '-d', '3']
        log_event("Test 2: Guest bruker", "DEBUG")
        result2 = subprocess.run(smb_cmd2, capture_output=True, text=True)
        log_event(f"Resultat 2: {result2.stderr}", "DEBUG")

    except Exception as e:
        log_event(f"Feil ved SMB testing: {str(e)}", "ERROR")


def get_server_users(ip):
    """Forsøker å hente brukerinformasjon fra serveren"""
    log_event(f"=== Starter brukeranalyse for {ip} ===", "DEBUG")

    # Test standard brukernavn
    test_users = ['Administrator', 'admin', 'guest']

    for user in test_users:
        try:
            log_event(f"Tester SMB tilkobling med bruker: {user}", "DEBUG")
            cmd = ['smbclient', '-L', f'//{ip}', '-U', f'{user}%', '-d', '3']
            result = subprocess.run(cmd, capture_output=True, text=True)

            if "NT_STATUS_ACCESS_DENIED" in result.stderr:
                log_event(f"Bruker {user} eksisterer men krever passord", "INFO")
            elif "NT_STATUS_LOGON_FAILURE" in result.stderr:
                log_event(f"Bruker {user} finnes ikke", "DEBUG")
            else:
                log_event(f"Interessant respons for {user}:\n{result.stderr}", "WARNING")

        except Exception as e:
            log_event(f"Feil ved testing av bruker {user}: {str(e)}", "ERROR")


def main():
    log_event("=== Starter utvidet serveranalyse med debugging ===", "INFO")

    target_ip = "192.168.1.170"
    log_event(f"Tester spesifikk IP: {target_ip}", "INFO")

    debug_network_info(target_ip)
    get_server_users(target_ip)

    log_event("=== Analyse fullført ===", "INFO")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log_event("\nAnalyse avbrutt av bruker", "WARNING")
        sys.exit(0)
    except Exception as e:
        log_event(f"Kritisk feil: {str(e)}", "ERROR")
        log_event("Stacktrace:", "ERROR")
        import traceback
        log_event(traceback.format_exc(), "ERROR")
        sys.exit(1)
