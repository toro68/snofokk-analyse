"""
Plowman API-klient for å hente brøytedata.

Henter siste brøytetidspunkt fra Plowman-kartet:
https://plowman-new.snøbrøyting.net/nb/share/Y3VzdG9tZXItMTM=

Customer ID: 13 (dekoded fra base64 "Y3VzdG9tZXItMTM=")
"""

import base64
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import requests

logger = logging.getLogger(__name__)


@dataclass
class PlowingEvent:
    """Representerer en brøytehendelse."""
    timestamp: datetime
    vehicle_id: Optional[str] = None
    vehicle_name: Optional[str] = None
    sector_name: Optional[str] = None
    distance_km: Optional[float] = None
    
    def hours_since(self) -> float:
        """Beregn timer siden brøyting."""
        now = datetime.now(timezone.utc)
        if self.timestamp.tzinfo is None:
            # Anta UTC hvis ingen tidssone
            ts = self.timestamp.replace(tzinfo=timezone.utc)
        else:
            ts = self.timestamp
        return (now - ts).total_seconds() / 3600


class PlowmanClient:
    """
    Klient for Plowman brøytekart API.
    
    Henter brøytedata fra det offentlige delekartet.
    """
    
    # Base URL for Plowman API
    BASE_URL = "https://plowman-new.xn--snbryting-m8ac.net"
    
    # Share ID for Fjellbergsskardet (base64 encoded "customer-13")
    SHARE_ID = "Y3VzdG9tZXItMTM="
    
    def __init__(self, share_id: str = None):
        """
        Initialiser Plowman-klienten.
        
        Args:
            share_id: Base64-encoded share ID (default: Fjellbergsskardet)
        """
        self.share_id = share_id or self.SHARE_ID
        self.customer_id = self._decode_customer_id(self.share_id)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Referer': f'{self.BASE_URL}/nb/share/{self.share_id}',
        })
    
    def _decode_customer_id(self, share_id: str) -> int:
        """Dekod customer ID fra base64 share ID."""
        try:
            decoded = base64.b64decode(share_id).decode('utf-8')
            # Format: "customer-13"
            if decoded.startswith('customer-'):
                return int(decoded.split('-')[1])
        except Exception as e:
            logger.warning(f"Kunne ikke dekode share_id: {e}")
        return 13  # Default
    
    def get_last_plowing(self, sector_name: str = None) -> Optional[PlowingEvent]:
        """
        Hent siste brøytetidspunkt.
        
        Args:
            sector_name: Filtrer på spesifikk rode/sektor (optional)
            
        Returns:
            PlowingEvent eller None hvis ingen data
        """
        try:
            # Prøv ulike API-endepunkter
            endpoints = [
                f'/api/public/activity/{self.customer_id}',
                f'/api/public/sectors/{self.customer_id}',
                f'/api/activity/{self.customer_id}',
                f'/api/sectors/{self.customer_id}/last-activity',
            ]
            
            for endpoint in endpoints:
                try:
                    response = self.session.get(
                        f'{self.BASE_URL}{endpoint}',
                        timeout=10
                    )
                    if response.status_code == 200:
                        data = response.json()
                        return self._parse_activity_data(data, sector_name)
                except requests.RequestException:
                    continue
            
            logger.warning("Ingen API-endepunkter svarte")
            return None
            
        except Exception as e:
            logger.error(f"Feil ved henting av brøytedata: {e}")
            return None
    
    def get_sectors(self) -> list[dict]:
        """
        Hent liste over roder/sektorer.
        
        Returns:
            Liste med sektorer og deres siste aktivitet
        """
        try:
            response = self.session.get(
                f'{self.BASE_URL}/api/public/sectors/{self.customer_id}',
                timeout=10
            )
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.error(f"Feil ved henting av sektorer: {e}")
        return []
    
    def get_vehicles(self) -> list[dict]:
        """
        Hent liste over kjøretøy.
        
        Returns:
            Liste med kjøretøy og deres status
        """
        try:
            response = self.session.get(
                f'{self.BASE_URL}/api/public/units/{self.customer_id}',
                timeout=10
            )
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.error(f"Feil ved henting av kjøretøy: {e}")
        return []
    
    def _parse_activity_data(self, data: dict | list, sector_name: str = None) -> Optional[PlowingEvent]:
        """Parse aktivitetsdata og finn siste brøyting."""
        try:
            activities = []
            
            if isinstance(data, list):
                activities = data
            elif isinstance(data, dict):
                activities = data.get('activities', data.get('data', []))
            
            if not activities:
                return None
            
            # Filtrer på sektor hvis spesifisert
            if sector_name:
                activities = [
                    a for a in activities 
                    if sector_name.lower() in str(a.get('sector', a.get('sectorName', ''))).lower()
                ]
            
            # Finn nyeste aktivitet
            latest = None
            latest_time = None
            
            for activity in activities:
                # Prøv ulike timestamp-felt
                timestamp_str = (
                    activity.get('lastActivity') or
                    activity.get('timestamp') or
                    activity.get('endTime') or
                    activity.get('created_at')
                )
                
                if timestamp_str:
                    try:
                        if isinstance(timestamp_str, str):
                            # Håndter ulike datoformater
                            for fmt in [
                                '%Y-%m-%dT%H:%M:%S.%fZ',
                                '%Y-%m-%dT%H:%M:%SZ',
                                '%Y-%m-%dT%H:%M:%S%z',
                                '%Y-%m-%d %H:%M:%S',
                            ]:
                                try:
                                    ts = datetime.strptime(timestamp_str, fmt)
                                    if ts.tzinfo is None:
                                        ts = ts.replace(tzinfo=timezone.utc)
                                    break
                                except ValueError:
                                    continue
                            else:
                                continue
                        elif isinstance(timestamp_str, (int, float)):
                            # Unix timestamp
                            ts = datetime.fromtimestamp(timestamp_str, tz=timezone.utc)
                        else:
                            continue
                        
                        if latest_time is None or ts > latest_time:
                            latest_time = ts
                            latest = activity
                    except Exception:
                        continue
            
            if latest and latest_time:
                return PlowingEvent(
                    timestamp=latest_time,
                    vehicle_id=str(latest.get('unitId', latest.get('vehicleId', ''))),
                    vehicle_name=latest.get('unitName', latest.get('vehicleName')),
                    sector_name=latest.get('sectorName', latest.get('sector')),
                    distance_km=latest.get('distance', latest.get('totalDistance')),
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Feil ved parsing av aktivitetsdata: {e}")
            return None
    
    def scrape_from_page(self) -> Optional[PlowingEvent]:
        """
        Scrape brøytedata direkte fra HTML-siden.
        
        Henter GeoJSON-data fra Next.js-applikasjonen.
        Finner lastUpdated-tidspunkter som er encoded som "$D2025-11-27T11:20:34.000Z".
        """
        try:
            import re
            
            response = self.session.get(
                f'{self.BASE_URL}/nb/share/{self.share_id}',
                timeout=15
            )
            
            if response.status_code != 200:
                logger.warning(f"Plowman share-side returnerte {response.status_code}")
                return None
            
            html = response.text
            
            # Next.js encoder datoer som "$D<ISO-timestamp>"
            # Finn alle lastUpdated-tidspunkter i GeoJSON-dataene
            pattern = r'\$D(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z)'
            matches = re.findall(pattern, html)
            
            if matches:
                # Finn nyeste tidspunkt
                latest_date = max(matches)
                ts = datetime.fromisoformat(latest_date.replace('Z', '+00:00'))
                logger.info(f"Fant siste brøyting: {ts}")
                return PlowingEvent(timestamp=ts)
            
            logger.warning("Ingen lastUpdated-tidspunkter funnet i HTML")
            return None
            
        except Exception as e:
            logger.error(f"Feil ved scraping: {e}")
            return None


def get_last_plowing_time(sector_name: str = None) -> Optional[PlowingEvent]:
    """
    Hjelpefunksjon for å hente siste brøytetidspunkt.
    
    Args:
        sector_name: Filtrer på spesifikk rode (optional)
        
    Returns:
        PlowingEvent eller None
    """
    client = PlowmanClient()
    
    # Prøv API først
    event = client.get_last_plowing(sector_name)
    
    # Fallback til scraping
    if event is None:
        event = client.scrape_from_page()
    
    return event


if __name__ == "__main__":
    # Test
    logging.basicConfig(level=logging.DEBUG)
    
    print("Tester Plowman API...")
    print(f"Customer ID: {PlowmanClient().customer_id}")
    
    event = get_last_plowing_time()
    if event:
        print(f"\nSiste brøyting:")
        print(f"  Tidspunkt: {event.timestamp}")
        print(f"  Timer siden: {event.hours_since():.1f}")
        print(f"  Kjøretøy: {event.vehicle_name or 'Ukjent'}")
        print(f"  Rode: {event.sector_name or 'Ukjent'}")
    else:
        print("\nKunne ikke hente brøytedata")
