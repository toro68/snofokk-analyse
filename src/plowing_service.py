"""
Brøytingsdata-tjeneste.

Henter data fra Plowman livekart og gir informasjon om siste brøyting
for å justere varsler i appen.
"""

import json
import re
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

# Cache-fil for brøytingsdata
CACHE_FILE = Path(__file__).parent.parent / "data" / "cache" / "plowing_cache.json"
PLOWMAN_HTML_FILE = Path(__file__).parent.parent / "plowman_page.html"

# Hvor lenge siden brøyting skal anses som "nylig" (timer)
RECENT_PLOWING_HOURS = 24


@dataclass
class PlowingInfo:
    """Informasjon om siste brøyting."""
    last_plowing: Optional[datetime]
    hours_since: Optional[float]
    is_recent: bool
    all_timestamps: list[datetime]
    source: str  # 'live', 'cache', 'none'
    error: Optional[str] = None
    
    @property
    def formatted_time(self) -> str:
        """Formattert tidspunkt for visning."""
        if not self.last_plowing:
            return "Ukjent"
        
        # Konverter til lokal tid (Norge)
        local_time = self.last_plowing.astimezone()
        now = datetime.now(timezone.utc)
        diff = now - self.last_plowing
        
        if diff.days == 0:
            if diff.seconds < 3600:
                return f"For {diff.seconds // 60} min siden"
            else:
                return f"I dag kl. {local_time.strftime('%H:%M')}"
        elif diff.days == 1:
            return f"I går kl. {local_time.strftime('%H:%M')}"
        elif diff.days < 7:
            dag_navn = ["man", "tir", "ons", "tor", "fre", "lør", "søn"]
            return f"{dag_navn[local_time.weekday()]} {local_time.strftime('%d.%m kl. %H:%M')}"
        else:
            return local_time.strftime("%d.%m.%Y kl. %H:%M")
    
    @property
    def status_emoji(self) -> str:
        """Emoji basert på hvor lenge siden siste brøyting."""
        if not self.last_plowing:
            return "❓"
        
        if self.hours_since is not None:
            if self.hours_since < 6:
                return "✅"  # Nylig brøytet
            elif self.hours_since < 24:
                return "🟢"  # Brøytet siste døgn
            elif self.hours_since < 48:
                return "🟡"  # 1-2 dager
            else:
                return "🟠"  # Mer enn 2 dager
        return "❓"


def parse_timestamps_from_html(html_content: str) -> list[datetime]:
    """Parser tidsstempler fra Plowman HTML-data."""
    timestamps = []
    
    # Finn alle ISO-tidsstempler (2025-11-27T11:20:34.000Z format)
    pattern = r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?)'
    matches = re.findall(pattern, html_content)
    
    for match in matches:
        try:
            # Håndter både med og uten Z
            ts_str = match
            if not ts_str.endswith('Z'):
                ts_str += 'Z'
            # Fjern backslash hvis det finnes
            ts_str = ts_str.replace('\\', '')
            
            dt = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
            timestamps.append(dt)
        except ValueError:
            continue
    
    return timestamps


def get_plowing_info(use_cache: bool = True, max_cache_age_hours: int = 1) -> PlowingInfo:
    """
    Henter brøytingsinformasjon.
    
    Args:
        use_cache: Om cache skal brukes
        max_cache_age_hours: Maks alder på cache før ny henting
    
    Returns:
        PlowingInfo med siste brøytingstidspunkt og status
    """
    now = datetime.now(timezone.utc)
    
    # Sjekk cache først
    if use_cache and CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, 'r') as f:
                cache = json.load(f)
            
            cache_time = datetime.fromisoformat(cache['cached_at'])
            cache_age = (now - cache_time).total_seconds() / 3600
            
            if cache_age < max_cache_age_hours and cache.get('last_plowing'):
                last_plowing = datetime.fromisoformat(cache['last_plowing'])
                hours_since = (now - last_plowing).total_seconds() / 3600
                
                return PlowingInfo(
                    last_plowing=last_plowing,
                    hours_since=hours_since,
                    is_recent=hours_since < RECENT_PLOWING_HOURS,
                    all_timestamps=[datetime.fromisoformat(ts) for ts in cache.get('all_timestamps', [])],
                    source='cache'
                )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Cache-lesefeil: {e}")
    
    # Prøv å lese fra HTML-fil (fra siste fetch)
    if PLOWMAN_HTML_FILE.exists():
        try:
            with open(PLOWMAN_HTML_FILE, 'r') as f:
                html_content = f.read()
            
            timestamps = parse_timestamps_from_html(html_content)
            
            if timestamps:
                # Finn siste tidspunkt
                latest = max(timestamps)
                hours_since = (now - latest).total_seconds() / 3600
                
                # Lagre til cache
                _save_cache(latest, timestamps)
                
                return PlowingInfo(
                    last_plowing=latest,
                    hours_since=hours_since,
                    is_recent=hours_since < RECENT_PLOWING_HOURS,
                    all_timestamps=sorted(set(timestamps), reverse=True),
                    source='live'
                )
        except Exception as e:
            logger.warning(f"HTML-lesefeil: {e}")
    
    # Ingen data tilgjengelig
    return PlowingInfo(
        last_plowing=None,
        hours_since=None,
        is_recent=False,
        all_timestamps=[],
        source='none',
        error="Ingen brøytingsdata tilgjengelig"
    )


def _save_cache(last_plowing: datetime, all_timestamps: list[datetime]) -> None:
    """Lagrer brøytingsdata til cache."""
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        cache_data = {
            'last_plowing': last_plowing.isoformat(),
            'all_timestamps': [ts.isoformat() for ts in sorted(set(all_timestamps), reverse=True)[:20]],
            'cached_at': datetime.now(timezone.utc).isoformat()
        }
        
        with open(CACHE_FILE, 'w') as f:
            json.dump(cache_data, f, indent=2)
    except Exception as e:
        logger.warning(f"Kunne ikke lagre cache: {e}")


def should_show_snow_warning(plowing_info: PlowingInfo, snow_cm: float) -> bool:
    """
    Vurderer om snøvarsel bør vises basert på brøyting.
    
    Logikk:
    - Hvis brøytet siste 6 timer: Ignorer snømengder < 10cm
    - Hvis brøytet siste 12 timer: Ignorer snømengder < 5cm
    - Ellers: Vis alle varsler
    """
    if not plowing_info.is_recent or plowing_info.hours_since is None:
        return True  # Vis alltid varsel hvis ingen brøytingsdata
    
    if plowing_info.hours_since < 6:
        # Nylig brøytet - høyere terskel
        return snow_cm >= 10
    elif plowing_info.hours_since < 12:
        # Brøytet i dag - moderat terskel
        return snow_cm >= 5
    else:
        # Mer enn 12 timer - normal terskel
        return snow_cm >= 3


def get_adjusted_risk_message(original_message: str, plowing_info: PlowingInfo) -> str:
    """
    Justerer risikomelding basert på brøyting.
    
    Legger til kontekst om når det ble brøytet.
    """
    if plowing_info.is_recent and plowing_info.last_plowing:
        return f"{original_message} (Sist brøytet: {plowing_info.formatted_time})"
    return original_message


# Hovedfunksjon for å teste modulen
if __name__ == "__main__":
    info = get_plowing_info()
    print(f"Siste brøyting: {info.formatted_time}")
    print(f"Timer siden: {info.hours_since:.1f}" if info.hours_since else "Ukjent")
    print(f"Er nylig: {info.is_recent}")
    print(f"Kilde: {info.source}")
    print(f"Status: {info.status_emoji}")
    
    if info.all_timestamps:
        print(f"\nAlle tidsstempler ({len(info.all_timestamps)}):")
        for ts in info.all_timestamps[:5]:
            print(f"  {ts.isoformat()}")
