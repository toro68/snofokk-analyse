# Noen tanker om glatte veier:
## Kritiske faktorer:
Temperaturendringer rundt 0°C
Forskjell mellom luft- og overflatetemperatur
Duggpunkt i forhold til overflatetemperatur
Nedbørstype og -mengde
Ulike typer glatte veier:
Rimfrost (når bakken er kaldere enn luften)
Svart is (når regn fryser på kald bakke)
Snø som har smeltet og frosset
Slaps (delvis smeltet snø)
Manglende data som kunne vært nyttig:
Direkte veitemperaturmålinger
Saltmengde på veien
Trafikkmengde (påvirker friksjonsvarme)
Soleksponering
Bakkestruktur/helning
Mulige utvidelser:
Koble mot Vegvesenet sine data
Bruke historiske ulykkesdata
Inkludere værvarsler for preventive tiltak
Legge til lokale forhold (skygge, broer, etc.)
Vi kan bruke mange av de samme datastrukturene og metodene som i snøfokk-analysen, men med andre grenseverdier og kombinasjoner av parametre.

# Frost API konfigurasjon for glatte veier
FROST_STATION_ID = "SN46220"

# Relevante parametre for glatte veier
FROST_PARAMETERS = [
    # Temperatur (kritisk for type is/glatthet)
    'air_temperature',              # Lufttemperatur
    'surface_temperature',          # Veitemperatur
    'min(air_temperature PT1H)',    # Minimumstemperatur
    'max(air_temperature PT1H)',    # Maksimumstemperatur
    'dew_point_temperature',        # Duggpunkt - viktig for rimfrost
    
    # Fuktighet (avgjørende for isdannelse)
    'relative_humidity',            # Luftfuktighet
    
    # Nedbør (type og mengde)
    'sum(precipitation_amount PT1H)',     # Nedbørsmengde
    'sum(duration_of_precipitation PT1H)', # Nedbørsvarighet
    'accumulated(precipitation_amount)',   # Total nedbør
    'over_time(gauge_content_difference PT1H)', # Endring i nedbør
]

# Foreslåtte grenser for glatte veier
PARAMETER_BOUNDS = {
    # Temperaturgrenser
    "temp_critical": (-5, 2),      # Mest kritisk område for isdannelse
    "temp_frost": (-8, -3),        # Område for rimfrost
    "temp_gradient": (0.5, 3),     # Temperaturendring per time
    "surface_air_diff": (-3, 3),   # Forskjell mellom vei og luft
    
    # Fuktighetsgrenser
    "humidity_frost": (75, 100),   # % - Kritisk for rimfrost
    "dew_point_diff": (-2, 2),     # Forskjell mellom temp og duggpunkt
    
    # Nedbørsgrenser
    "precip_light": (0.1, 1),      # mm/t - Lett nedbør
    "precip_moderate": (1, 3),     # mm/t - Moderat nedbør
    "precip_heavy": (3, 10),       # mm/t - Kraftig nedbør
}

# Typer glatte veier vi kan identifisere
ROAD_CONDITIONS = {
    "FROST": {
        # Rim på veien
        "temp_max": 2,
        "humidity_min": 75,
        "surface_temp_max": 0
    },
    "BLACK_ICE": {
        # Svart is
        "temp_range": (-5, 2),
        "precip_required": True,
        "temp_falling": True
    },
    "SLUSH": {
        # Slaps
        "temp_range": (0, 3),
        "precip_required": True
    },
    "SNOW_ICE": {
        # Snø som har frosset
        "temp_falling": True,
        "temp_range": (-10, 0),
        "snow_required": True
    }
}