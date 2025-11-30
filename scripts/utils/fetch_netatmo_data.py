#!/usr/bin/env python3
import json
import os
import time
from datetime import datetime

import requests


def load_config():
    """Laster konfigurasjon fra config/alert_config.json"""
    config_path = os.path.join(
        os.path.dirname(__file__),
        '..',
        'config',
        'alert_config.json'
    )
    with open(config_path) as f:
        return json.load(f)


class NetatmoPublicClient:
    def __init__(self, client_id, client_secret, username, password):
        self.client_id = client_id
        self.client_secret = client_secret
        self.username = username
        self.password = password
        self.token = None
        self.refresh_token = None
        self.token_expires = 0

    def get_token(self):
        """Henter eller fornyer OAuth token."""
        if self.token and time.time() < self.token_expires:
            return self.token

        # Hvis vi har en refresh token, prøv å bruke den først
        if self.refresh_token:
            try:
                return self._refresh_token()
            except requests.exceptions.RequestException:
                print("Kunne ikke fornye token, prøver ny autentisering...")

        # Hvis ikke, eller hvis refresh feilet, gjør ny autentisering
        return self._authenticate()

    def _authenticate(self):
        """Autentiserer med client credentials."""
        payload = {
            'grant_type': 'password',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'username': self.username,
            'password': self.password,
            'scope': 'read_station'
        }

        try:
            print("Autentiserer mot Netatmo...")
            print(
                "Merk: Sjekk at appen er aktivert på "
                "https://dev.netatmo.com/apps/"
            )
            print(
                "og at 'Public Weather API' er aktivert "
                "under 'App Permissions'"
            )

            response = requests.post(
                'https://api.netatmo.com/oauth2/token',
                data=payload
            )

            if response.status_code == 403:
                print("\nFEIL: Appen ser ut til å være deaktivert.")
                print("1. Gå til https://dev.netatmo.com/apps/")
                print("2. Velg appen 'fjellbs'")
                print("3. Aktiver appen")
                print(
                    "4. Sjekk at 'Public Weather API' er aktivert "
                    "under 'App Permissions'"
                )
                print("5. Prøv igjen\n")
                raise Exception("App deaktivert")

            response.raise_for_status()
            token_data = response.json()
            print("Autentisering vellykket!")

            self.token = token_data['access_token']
            refresh_token = token_data.get('refresh_token')
            if refresh_token:
                self.refresh_token = refresh_token
            self.token_expires = time.time() + token_data['expires_in']
            return self.token
        except requests.exceptions.RequestException as e:
            print(f"\nFeil ved autentisering: {e}")
            if hasattr(e, 'response'):
                print(f"Response status: {e.response.status_code}")
                print(f"Response body: {e.response.text}")

                if e.response.status_code == 400:
                    print("\nMulige løsninger:")
                    print("1. Sjekk at brukernavn og passord er riktig")
                    print("2. Gå til https://dev.netatmo.com/apps/")
                    print("3. Velg appen 'fjellbs'")
                    print("4. Klikk 'Reset keys' for å generere nye nøkler")
                    print("5. Oppdater client_id og client_secret i scriptet")
                    print("6. Prøv igjen\n")
            raise

    def _refresh_token(self):
        """Fornyer token med refresh token."""
        payload = {
            'grant_type': 'refresh_token',
            'refresh_token': self.refresh_token,
            'client_id': self.client_id,
            'client_secret': self.client_secret
        }

        try:
            print("Fornyer token...")
            response = requests.post(
                'https://api.netatmo.com/oauth2/token',
                data=payload
            )
            response.raise_for_status()
            token_data = response.json()
            print("Token fornyet!")

            self.token = token_data['access_token']
            new_refresh = token_data.get('refresh_token')
            if new_refresh:
                self.refresh_token = new_refresh
            self.token_expires = time.time() + token_data['expires_in']
            return self.token
        except requests.exceptions.RequestException as e:
            print(f"Feil ved fornyelse av token: {e}")
            raise

    def get_public_data(
        self,
        lat_ne,
        lon_ne,
        lat_sw,
        lon_sw,
        required_data=None
    ):
        """
        Henter offentlige data fra Netatmo-stasjoner i et definert område.

        Args:
            lat_ne: Nordøst breddegrad
            lon_ne: Nordøst lengdegrad
            lat_sw: Sørvest breddegrad
            lon_sw: Sørvest lengdegrad
            required_data: Liste med ønskede måledata (temp, humidity, etc.)
        """
        if required_data is None:
            required_data = ["temperature"]

        # Hent token først
        token = self.get_token()

        headers = {
            'Authorization': f'Bearer {token}'
        }

        params = {
            'lat_ne': lat_ne,
            'lon_ne': lon_ne,
            'lat_sw': lat_sw,
            'lon_sw': lon_sw,
            'required_data': ','.join(required_data)
        }

        try:
            print(f"Bruker token: {token[:20]}...")
            response = requests.get(
                'https://api.netatmo.com/api/getpublicdata',
                headers=headers,
                params=params
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Feil ved henting av data: {e}")
            if hasattr(e, 'response'):
                print(f"Response status: {e.response.status_code}")
                print(f"Response body: {e.response.text}")
            raise


def save_data(data, output_dir):
    """Lagrer data til JSON-fil med tidsstempel."""
    # Konverter relativ sti til absolutt sti
    if not os.path.isabs(output_dir):
        output_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            output_dir
        )

    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = os.path.join(output_dir, f'netatmo_data_{timestamp}.json')

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Data lagret til {filename}")


def main():
    # Konfigurasjon for Suldal-området (med ca 4km radius)
    netatmo_config = {
        'lat_ne': 59.42,  # Nordøst breddegrad
        'lon_ne': 6.45,   # Nordøst lengdegrad
        'lat_sw': 59.37,  # Sørvest breddegrad
        'lon_sw': 6.40,   # Sørvest lengdegrad
        'client_id': '677372fabe5b81bad4081a9d',
        'client_secret': 'SmlGKkg7kTKndnuERhle30G3VXZVSnJiJHqX1Ldd',
        'username': 'tor.jossang@gmail.com',
        'password': '4HbgpQlNV56H',
        'output_dir': 'data/raw/netatmo'  # Relativ sti fra prosjektrot
    }

    try:
        print("Starter Netatmo API-kall...")
        client = NetatmoPublicClient(
            netatmo_config['client_id'],
            netatmo_config['client_secret'],
            netatmo_config['username'],
            netatmo_config['password']
        )

        # Sett tokens direkte
        client.token = (
            '57cb06764c5a882cc18b45f8|'
            '6e1d9c266dd6fbf11c67c29828254608'
        )
        client.refresh_token = (
            '57cb06764c5a882cc18b45f8|'
            '4768026fa2522e26256ee9dec91c4a3b'
        )
        client.token_expires = time.time() + 10800  # 3 timer

        print("Henter værdata...")
        data = client.get_public_data(
            netatmo_config['lat_ne'],
            netatmo_config['lon_ne'],
            netatmo_config['lat_sw'],
            netatmo_config['lon_sw']
        )
        print("Værdata hentet, lagrer til fil...")
        save_data(data, netatmo_config['output_dir'])
        print("Ferdig!")

    except Exception as e:
        print(f"En feil oppstod: {e}")
        if hasattr(e, 'response'):
            print(f"Response status: {e.response.status_code}")
            print(f"Response body: {e.response.text}")

            if e.response.status_code == 403:
                print("\nFEIL: Sjekk at:")
                print("1. Appen er aktivert på https://dev.netatmo.com/apps/")
                print("2. 'Public Weather API' er aktivert")
                print("3. Token er gyldig")
            elif e.response.status_code == 400:
                print("\nFEIL: Sjekk at:")
                print("1. Token-format er riktig")
                print("2. Token ikke er utløpt")


if __name__ == "__main__":
    main()
