#!/usr/bin/env python3

import glob
import json
import os
from datetime import datetime

import folium
from selenium import webdriver
from selenium.webdriver.chrome.options import Options


def get_latest_data():
    """Henter nyeste data fra netatmo-filene."""
    data_dir = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'data/raw/netatmo'
    )
    files = glob.glob(os.path.join(data_dir, 'netatmo_data_*.json'))
    if not files:
        raise FileNotFoundError("Ingen netatmo-datafiler funnet")

    latest_file = max(files, key=os.path.getctime)
    with open(latest_file) as f:
        return json.load(f)


def create_weather_map(data):
    """Lager et kart med værstasjoner og deres målinger."""
    # Finn senterpunkt for kartet
    stations = data['body']
    if not stations:
        raise ValueError("Ingen værstasjoner funnet i dataene")

    print(f"Fant {len(stations)} værstasjoner")

    # Opprett kartet med mer zoom
    m = folium.Map(
        location=[59.39402, 6.42497],  # Sett fast senterpunkt
        zoom_start=13,  # Økt zoom-nivå
        tiles='CartoDB positron'  # Lysere kartstil
    )

    # Legg til markører for hver stasjon
    for station in stations:
        location = station['place']['location']
        measures = station['measures']

        # Finn temperatur, luftfuktighet og lufttrykk
        temp = None
        humidity = None
        pressure = None
        wind = None

        for _module_id, module_data in measures.items():
            # Sjekk temperatur og luftfuktighet
            if 'type' in module_data and 'temperature' in module_data['type']:
                res = module_data['res']
                latest_time = max(res.keys())
                measurements = res[latest_time]
                temp = measurements[0]
                if len(measurements) > 1:
                    humidity = measurements[1]

            # Sjekk lufttrykk
            elif 'type' in module_data and 'pressure' in module_data['type']:
                res = module_data['res']
                latest_time = max(res.keys())
                pressure = res[latest_time][0]

            # Sjekk vind hvis tilgjengelig
            elif 'wind_strength' in module_data:
                wind = {
                    'strength': module_data['wind_strength'],
                    'gust': module_data['gust_strength'],
                    'angle': module_data['wind_angle']
                }

        # Lag popup-tekst med mer informasjon
        place = station['place']
        popup_text = (
            f"<b>Sted:</b> {place.get('street', 'Ukjent')}<br>"
            f"<b>Høyde:</b> {place.get('altitude', 'Ukjent')}m<br>"
        )
        if temp is not None:
            popup_text += f"<b>Temperatur:</b> {temp}°C<br>"
        if humidity is not None:
            popup_text += f"<b>Luftfuktighet:</b> {humidity}%<br>"
        if pressure is not None:
            popup_text += f"<b>Lufttrykk:</b> {pressure} hPa<br>"
        if wind is not None:
            popup_text += (
                f"<b>Vind:</b> {wind['strength']} m/s<br>"
                f"<b>Vindkast:</b> {wind['gust']} m/s<br>"
                f"<b>Vindretning:</b> {wind['angle']}°<br>"
            )

        # Velg farge basert på temperatur
        if temp is not None:
            if temp < -5:
                color = '#0000FF'  # Mørkeblå
            elif temp < -2:
                color = '#4169E1'  # Kongeblå
            elif temp < 0:
                color = '#87CEEB'  # Himmelblå
            elif temp < 2:
                color = '#98FB98'  # Lysegrønn
            elif temp < 5:
                color = '#32CD32'  # Limegrønn
            else:
                color = '#FF4500'  # Oransjerød
        else:
            color = '#808080'  # Grå

        # Legg til markør med større radius og mer synlig outline
        folium.CircleMarker(
            location=[location[1], location[0]],
            radius=12,
            popup=popup_text,
            color='black',      # Svart outline
            weight=2,           # Tykkere outline
            fill=True,
            fill_color=color,
            fill_opacity=0.7    # Litt gjennomsiktig
        ).add_to(m)

    # Legg til fargeforklaring
    legend_html = """
    <div style="position: fixed; bottom: 50px; left: 50px; z-index: 1000; background-color: white;
    padding: 10px; border: 2px solid grey; border-radius: 5px;">
    <p><strong>Temperatur</strong></p>
    <p><span style="color:#0000FF">■</span> Under -5°C</p>
    <p><span style="color:#4169E1">■</span> -5°C til -2°C</p>
    <p><span style="color:#87CEEB">■</span> -2°C til 0°C</p>
    <p><span style="color:#98FB98">■</span> 0°C til 2°C</p>
    <p><span style="color:#32CD32">■</span> 2°C til 5°C</p>
    <p><span style="color:#FF4500">■</span> Over 5°C</p>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    return m


def save_map_as_png(map_obj, output_path):
    """Lagrer folium-kartet som PNG-fil."""
    # Lagre kartet som HTML først
    html_path = output_path.replace('.png', '.html')
    map_obj.save(html_path)

    # Konfigurer Chrome i headless mode
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    # Start Chrome og ta skjermbilde
    driver = webdriver.Chrome(options=chrome_options)
    driver.get(f'file://{os.path.abspath(html_path)}')
    driver.set_window_size(1200, 800)  # Sett størrelse på kartet

    # Vent litt for å la kartet laste
    driver.implicitly_wait(5)

    # Ta skjermbilde
    driver.save_screenshot(output_path)
    driver.quit()

    # Fjern midlertidig HTML-fil
    os.remove(html_path)


def main():
    try:
        # Hent nyeste data
        print("Henter værdata...")
        data = get_latest_data()

        # Lag kart
        print("Genererer kart...")
        weather_map = create_weather_map(data)

        # Lagre som PNG
        output_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'data/maps'
        )
        os.makedirs(output_dir, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = os.path.join(
            output_dir,
            f'weather_map_{timestamp}.png'
        )

        print("Lagrer kart som PNG...")
        save_map_as_png(weather_map, output_path)
        print(f"Kart lagret til: {output_path}")

    except Exception as e:
        print(f"En feil oppstod: {e}")


if __name__ == "__main__":
    main()
