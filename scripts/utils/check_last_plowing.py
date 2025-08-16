#!/usr/bin/env python3
import json
import traceback
from datetime import UTC, datetime
from pprint import pprint
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup


def debug_timestamp(ts_str):
    """Hjelpefunksjon for å debugge tidspunkt-parsing"""
    print(f"\nDebugging timestamp: {ts_str}")
    print(f"Original format   : {ts_str}")
    clean_ts = ts_str.replace('$D', '')
    print(f"Etter $D fjerning : {clean_ts}")

    try:
        dt_utc = datetime.strptime(
            clean_ts,
            '%Y-%m-%dT%H:%M:%S.%fZ'
        ).replace(tzinfo=UTC)
        print(f"Parset UTC      : {dt_utc}")
        print(f"UTC timestamp   : {dt_utc.timestamp()}")

        dt_oslo = dt_utc.astimezone(ZoneInfo('Europe/Oslo'))
        print(f"Konvertert Oslo : {dt_oslo}")
        print(f"Oslo timestamp  : {dt_oslo.timestamp()}")
        return dt_utc, dt_oslo
    except ValueError as e:
        print(f"Parsing error   : {e}")
        return None, None

print("\nHenter siste brøytetidspunkt fra Fjellbergsskardet...")

try:
    url = "https://plowman-new.xn--snbryting-m8ac.net/nb/share/Y3VzdG9tZXItMTM="
    response = requests.get(url, timeout=10)

    if not response.ok:
        print(f"Feil ved henting av data. Status: {response.status_code}")
        exit(1)

    soup = BeautifulSoup(response.text, 'html.parser')
    scripts = soup.find_all('script')

    if len(scripts) >= 29:
        script = scripts[28]
        if script.string:
            content = script.string.strip()

            if 'self.__next_f.push' in content:
                content = content.replace('self.__next_f.push([1,"', '')
                content = content.replace('"])', '')
                content = content.replace('\\"', '"')

                if '{"dictionary"' in content:
                    start = content.find('{"dictionary"')
                    end = content.rfind('}') + 1
                    json_str = content[start:end]
                    data = json.loads(json_str)

                    print("\n=== RÅDATA FRA API ===")
                    print("Features fra GeoJSON:")
                    for i, feature in enumerate(data.get('geojson', {}).get("features", []), 1):
                        props = feature.get("properties", {})
                        print(f"\nFeature {i}:")
                        print("Properties:")
                        pprint(props, indent=2)
                        if props.get("lastUpdated"):
                            dt_utc, dt_oslo = debug_timestamp(props["lastUpdated"])
                        else:
                            print("  Ingen lastUpdated verdi")
                    print("\n=== SLUTT RÅDATA ===\n")

                    # Finn alle tidspunkt
                    timestamps = []
                    for f in data.get('geojson', {}).get("features", []):
                        ts = f.get("properties", {}).get("lastUpdated")
                        if ts:
                            dt_utc, dt_oslo = debug_timestamp(ts)
                            if dt_utc and dt_oslo:
                                timestamps.append((dt_utc, dt_oslo))

                    if timestamps:
                        # Sorter etter UTC tid
                        timestamps.sort(key=lambda x: x[0])

                        print("\nAlle registrerte tidspunkt (nyeste først):")
                        print("----------------------------------------")
                        now_utc = datetime.now(UTC)
                        now_oslo = datetime.now(ZoneInfo('Europe/Oslo'))

                        print(f"Nåværende tid (UTC):  {now_utc.strftime('%Y-%m-%d %H:%M:%S %Z')}")
                        print(f"Nåværende tid (Oslo): {now_oslo.strftime('%Y-%m-%d %H:%M:%S %Z')}")
                        print("\nRegistrerte brøytetidspunkt:")

                        for utc_time, oslo_time in reversed(timestamps):
                            future = utc_time > now_utc
                            print(
                                f"UTC:  {utc_time.strftime('%Y-%m-%d %H:%M:%S %Z')}"
                                f"\nOslo: {oslo_time.strftime('%Y-%m-%d %H:%M:%S %Z')}"
                                f"{' ⚠️ FREMTIDIG TIDSPUNKT!' if future else ''}\n"
                            )

                        # Finn siste gyldige tidspunkt (ikke i fremtiden)
                        valid_timestamps = [
                            (utc, oslo) for utc, oslo in timestamps
                            if utc <= now_utc
                        ]

                        if valid_timestamps:
                            last_utc, last_oslo = valid_timestamps[-1]
                            print("\n🚜 Siste gyldige brøyting:")
                            print(f"UTC:  {last_utc.strftime('%Y-%m-%d %H:%M:%S %Z')}")
                            print(f"Oslo: {last_oslo.strftime('%d.%m.%Y kl. %H:%M')}\n")
                        else:
                            print("\n⚠️ ADVARSEL: Alle registrerte tidspunkt er i fremtiden!")
                            print("Dette kan tyde på feil i dataene fra brøytetjenesten.\n")

                        exit(0)

    print("\n❌ Fant ingen brøytedata\n")

except Exception as e:
    print(f"\n❌ Feil: {str(e)}\n")
    print("\nDetaljer:")
    print(traceback.format_exc())
    exit(1)
