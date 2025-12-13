#!/usr/bin/env python3
"""Sjekk værdata mot brøyteepisoder november 2025."""

import os

import requests
from dotenv import load_dotenv

load_dotenv()

client_id = os.getenv('FROST_CLIENT_ID')
if not client_id:
    print("FEIL: FROST_CLIENT_ID ikke funnet i .env")
    exit(1)

# Hent værdata for 22-27 november 2025
url = "https://frost.met.no/observations/v0.jsonld"
params = {
    'sources': 'SN46220',
    'elements': 'air_temperature,wind_speed,sum(precipitation_amount PT1H),surface_snow_thickness,dew_point_temperature,relative_humidity',
    'referencetime': '2025-11-22/2025-11-28',
    'timeresolutions': 'PT1H'
}

response = requests.get(url, params=params, auth=(client_id, ''))

if response.status_code == 200:
    data = response.json()

    # Organisér data per time
    hourly = {}
    for obs in data.get('data', []):
        time = obs['referenceTime'][:16]
        if time not in hourly:
            hourly[time] = {}
        for elem in obs.get('observations', []):
            hourly[time][elem['elementId']] = elem['value']

    print("=" * 80)
    print("VÆRDATA FOR BRØYTEEPISODER NOVEMBER 2025")
    print("=" * 80)
    print()
    print("BRØYTEEPISODER:")
    print("  22.11: Skraping 08:41-14:47 (6t 5m), Strøing 12:54-13:40 (46m)")
    print("  23.11: Strøing 09:25-10:50 (1t 25m)")
    print("  27.11: Skraping 07:23-11:55 (4t 32m), Strøing 08:46-09:27 + 10:26-11:47")
    print()

    for date in ["2025-11-22", "2025-11-23", "2025-11-27"]:
        print(f"\n{'='*60}")
        print(f"📅 {date}")
        print("-" * 60)
        print("  Time  | Temp    | Vind     | Nedbør | Snødybde | Duggpunkt")
        print("-" * 60)

        for hour in range(6, 16):
            time_key = f"{date}T{hour:02d}:00"
            if time_key in hourly:
                h = hourly[time_key]
                temp = h.get('air_temperature', None)
                wind = h.get('wind_speed', None)
                precip = h.get('sum(precipitation_amount PT1H)', 0)
                snow = h.get('surface_snow_thickness', None)
                dew = h.get('dew_point_temperature', None)

                temp_str = f"{temp:>6.1f}°C" if temp is not None else "   N/A  "
                wind_str = f"{wind:>5.1f} m/s" if wind is not None else "  N/A   "
                precip_str = f"{precip:>5.1f}mm" if precip else "  0.0mm"
                snow_str = f"{snow:>6.0f}cm" if snow is not None else "   N/A  "
                dew_str = f"{dew:>6.1f}°C" if dew is not None else "   N/A  "

                print(f"  {hour:02d}:00 | {temp_str} | {wind_str} | {precip_str} | {snow_str} | {dew_str}")
            else:
                print(f"  {hour:02d}:00 | (ingen data)")

    print()
    print("=" * 60)
    print("ANALYSE")
    print("=" * 60)

    # Analyser forhold
    for date, label in [("2025-11-22", "22.nov"), ("2025-11-23", "23.nov"), ("2025-11-27", "27.nov")]:
        temps = []
        winds = []
        precips = []
        snows = []
        dews = []

        for hour in range(6, 16):
            time_key = f"{date}T{hour:02d}:00"
            if time_key in hourly:
                h = hourly[time_key]
                if h.get('air_temperature') is not None:
                    temps.append(h['air_temperature'])
                if h.get('wind_speed') is not None:
                    winds.append(h['wind_speed'])
                if h.get('sum(precipitation_amount PT1H)'):
                    precips.append(h['sum(precipitation_amount PT1H)'])
                if h.get('surface_snow_thickness') is not None:
                    snows.append(h['surface_snow_thickness'])
                if h.get('dew_point_temperature') is not None:
                    dews.append(h['dew_point_temperature'])

        print(f"\n{label}:")
        if temps:
            print(f"  Temp: {min(temps):.1f} til {max(temps):.1f}°C (snitt {sum(temps)/len(temps):.1f}°C)")
        if dews:
            print(f"  Duggpunkt: {min(dews):.1f} til {max(dews):.1f}°C")
        if winds:
            print(f"  Vind: {min(winds):.1f} til {max(winds):.1f} m/s")
        if precips:
            print(f"  Nedbør: {sum(precips):.1f}mm totalt")
        else:
            print("  Nedbør: 0mm")
        if snows:
            print(f"  Snødybde: {min(snows):.0f} til {max(snows):.0f}cm")

        # Vurdering
        if temps:
            avg_temp = sum(temps)/len(temps)
            if avg_temp > 0 and precips:
                print("  ADVARSEL: SLAPS-RISIKO: Plusgrader + nedbør")
            elif avg_temp > 0:
                print("  ADVARSEL: SMELTING: Plusgrader kan gi slaps")
        if dews and temps:
            if max(dews) < 0 and sum(precips) > 0 if precips else False:
                print("  NYSNØ: Duggpunkt under 0°C + nedbør")

else:
    print(f"FEIL: API-feil: {response.status_code}")
    print(response.text[:500])
