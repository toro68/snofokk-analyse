"""
Brøytingsdata-tjeneste.

Henter data fra vedlikeholds-API og gir informasjon om siste brøyting
for å justere varsler i appen.
"""

import json
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from src.config import get_secret, settings
from src.plowman_client import get_last_maintenance_result

logger = logging.getLogger(__name__)

# Cache-fil for brøytingsdata
CACHE_FILE = Path(__file__).parent.parent / "data" / "cache" / "plowing_cache.json"

# Hvor lenge siden brøyting skal anses som "nylig" (timer)
RECENT_PLOWING_HOURS = settings.plowing_service.recent_plowing_hours


def _maintenance_keywords() -> set[str]:
    # Norsk + engelsk (API kan variere mellom systemer)
    return {
        "brøyting",
        "brøyte",
        "snøbrøyting",
        "plog",
        "plow",
        "plowing",
        "snowplow",
        "snow_plow",
        "skrap",
        "skrape",
        "skraping",
        "scrape",
        "scraping",
        "fres",
        "fresing",
        "milling",
        "strø",
        "strøing",
        "salt",
        "salting",
        "grit",
        "gritting",
        "sanding",
    }


def is_maintenance_action(plowing_info: "PlowingInfo") -> bool:
    """True hvis siste vedlikehold ser ut som brøyting/strøing.

Brukes for å kunne stoppe farevarsel når vedlikehold pågår / nettopp har skjedd.
"""

    haystacks: list[str] = []
    if plowing_info.last_event_type:
        haystacks.append(plowing_info.last_event_type)
    if plowing_info.last_work_types:
        haystacks.extend([str(x) for x in plowing_info.last_work_types])

    if not haystacks:
        return False

    keywords = _maintenance_keywords()
    for raw in haystacks:
        text = raw.lower()
        if any(k in text for k in keywords):
            return True
    return False


def should_suppress_alerts(plowing_info: "PlowingInfo") -> bool:
    """True hvis vi bør stanse farevarsler pga nylig vedlikehold.

Vinduet styres via env/secrets:
- MAINTENANCE_SUPPRESS_HOURS (default: 3.0)
"""

    if not plowing_info.last_plowing or plowing_info.hours_since is None:
        return False

    suppress_hours = get_maintenance_suppress_hours()

    if plowing_info.hours_since > suppress_hours:
        return False

    return is_maintenance_action(plowing_info)


def get_maintenance_suppress_hours() -> float:
    """Returnerer hvor lenge farevarsel skal stanses etter vedlikehold."""
    try:
        return float(get_secret("MAINTENANCE_SUPPRESS_HOURS", "3.0"))
    except ValueError:
        return 3.0


@dataclass
class PlowingInfo:
    """Informasjon om siste brøyting."""
    last_plowing: datetime | None
    hours_since: float | None
    is_recent: bool
    all_timestamps: list[datetime]
    source: str  # 'live', 'cache', 'none'
    error: str | None = None
    last_event_type: str | None = None
    last_work_types: list[str] | None = None
    last_operator_id: str | None = None

    @property
    def formatted_time(self) -> str:
        """Formattert tidspunkt for visning."""
        if not self.last_plowing:
            return "Ukjent"

        # Konverter til lokal tid (Norge)
        local_time = self.last_plowing.astimezone()
        now = datetime.now(UTC)
        diff = now - self.last_plowing
        cfg = settings.plowing_service

        if diff.days == 0:
            if diff.seconds < cfg.formatted_recent_seconds:
                return f"For {diff.seconds // 60} min siden"
            else:
                return f"I dag kl. {local_time.strftime('%H:%M')}"
        elif diff.days == 1:
            return f"I går kl. {local_time.strftime('%H:%M')}"
        elif diff.days < cfg.formatted_week_days:
            dag_navn = ["man", "tir", "ons", "tor", "fre", "lør", "søn"]
            return f"{dag_navn[local_time.weekday()]} {local_time.strftime('%d.%m kl. %H:%M')}"
        else:
            return local_time.strftime("%d.%m.%Y kl. %H:%M")

    @property
    def status_emoji(self) -> str:
        """Statusmarkør for UI.

        Appen bruker ikke emojis i UI.
        """
        return ""


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


def get_plowing_info(use_cache: bool = True, max_cache_age_hours: int | None = None) -> PlowingInfo:
    """
    Henter brøytingsinformasjon.

    Args:
        use_cache: Om cache skal brukes
        max_cache_age_hours: Maks alder på cache før ny henting

    Returns:
        PlowingInfo med siste brøytingstidspunkt og status
    """
    now = datetime.now(UTC)

    if max_cache_age_hours is None:
        max_cache_age_hours = settings.plowing_service.default_max_cache_age_hours

    cache_data = _load_cache()

    # Sjekk cache først
    if use_cache and cache_data:
        cache_age = (now - cache_data['cached_at']).total_seconds() / 3600
        if cache_age < max_cache_age_hours and cache_data['last_plowing']:
            last_plowing = cache_data['last_plowing']
            hours_since = (now - last_plowing).total_seconds() / 3600
            return PlowingInfo(
                last_plowing=last_plowing,
                hours_since=hours_since,
                is_recent=hours_since < RECENT_PLOWING_HOURS,
                all_timestamps=cache_data['all_timestamps'],
                source='cache',
                last_event_type=cache_data.get('last_event_type'),
                last_work_types=cache_data.get('last_work_types'),
                last_operator_id=cache_data.get('last_operator_id'),
            )

    # Hent live data fra vedlikeholds-API
    try:
        # Merk: client håndterer manglende secrets og returnerer meningsfull error.
        event, event_error = get_last_maintenance_result()

        if not event and event_error:
            return PlowingInfo(
                last_plowing=None,
                hours_since=None,
                is_recent=False,
                all_timestamps=cache_data['all_timestamps'] if cache_data else [],
                source='none',
                error=event_error,
            )

        if event and event.timestamp:
            newest_cached = cache_data['last_plowing'] if cache_data else None
            new_timestamp = event.timestamp

            if newest_cached and new_timestamp < newest_cached:
                logger.warning(
                    "Plowman returnerte eldre brøyting (%s) enn cache (%s) – beholder cache",
                    new_timestamp.isoformat(),
                    newest_cached.isoformat()
                )
                hours_since = (now - newest_cached).total_seconds() / 3600
                return PlowingInfo(
                    last_plowing=newest_cached,
                    hours_since=hours_since,
                    is_recent=hours_since < RECENT_PLOWING_HOURS,
                    all_timestamps=cache_data['all_timestamps'] if cache_data else [newest_cached],
                    source='cache',
                    last_event_type=cache_data.get('last_event_type') if cache_data else None,
                    last_work_types=cache_data.get('last_work_types') if cache_data else None,
                    last_operator_id=cache_data.get('last_operator_id') if cache_data else None,
                )

            # Lagre til cache og returner live-data
            updated_cache = _save_cache(
                [new_timestamp],
                existing_cache=cache_data,
                last_event_type=event.event_type or event.sector_name,
                last_work_types=event.work_types,
                last_operator_id=event.operator_id or event.vehicle_name,
            )
            hours_since = (now - new_timestamp).total_seconds() / 3600

            return PlowingInfo(
                last_plowing=new_timestamp,
                hours_since=hours_since,
                is_recent=hours_since < RECENT_PLOWING_HOURS,
                all_timestamps=updated_cache['all_timestamps'],
                source='live',
                last_event_type=updated_cache.get('last_event_type'),
                last_work_types=updated_cache.get('last_work_types'),
                last_operator_id=updated_cache.get('last_operator_id'),
            )
    except Exception as e:
        logger.warning(f"Feil ved henting fra vedlikeholds-API: {e}")

    # Ingen data tilgjengelig
    if cache_data and cache_data['last_plowing']:
        last_plowing = cache_data['last_plowing']
        hours_since = (now - last_plowing).total_seconds() / 3600
        return PlowingInfo(
            last_plowing=last_plowing,
            hours_since=hours_since,
            is_recent=hours_since < RECENT_PLOWING_HOURS,
            all_timestamps=cache_data['all_timestamps'],
            source='stale-cache',
            error="Live vedlikeholds-API utilgjengelig – viser cache",
            last_event_type=cache_data.get('last_event_type'),
            last_work_types=cache_data.get('last_work_types'),
            last_operator_id=cache_data.get('last_operator_id'),
        )

    return PlowingInfo(
        last_plowing=None,
        hours_since=None,
        is_recent=False,
        all_timestamps=[],
        source='none',
        error="Ingen brøytingsdata tilgjengelig"
    )


def _load_cache() -> dict | None:
    """Les cachefil og returner strukturert innhold."""
    if not CACHE_FILE.exists():
        return None

    try:
        with open(CACHE_FILE) as f:
            raw = json.load(f)

        cached_at = datetime.fromisoformat(raw['cached_at'])
        stored_timestamps = [
            datetime.fromisoformat(ts)
            for ts in raw.get('all_timestamps', [])
            if ts
        ]

        if raw.get('last_plowing'):
            stored_timestamps.append(datetime.fromisoformat(raw['last_plowing']))

        unique_sorted = _dedupe_and_sort(stored_timestamps)
        last_plowing = unique_sorted[0] if unique_sorted else None

        return {
            'cached_at': cached_at,
            'all_timestamps': unique_sorted,
            'last_plowing': last_plowing,
            'last_event_type': raw.get('last_event_type'),
            'last_work_types': raw.get('last_work_types'),
            'last_operator_id': raw.get('last_operator_id'),
        }
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        logger.warning(f"Cache-lesefeil: {e}")
        return None


def _save_cache(
    new_timestamps: list[datetime],
    existing_cache: dict | None = None,
    last_event_type: str | None = None,
    last_work_types: list[str] | None = None,
    last_operator_id: str | None = None,
) -> dict:
    """Lagrer brøytingsdata til cache og returnerer ny struktur."""
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

        existing = existing_cache['all_timestamps'] if existing_cache else []
        merged = _dedupe_and_sort(existing + new_timestamps)
        merged_limited = merged[:settings.plowing_service.cache_max_entries]

        cache_payload = {
            'last_plowing': merged_limited[0].isoformat() if merged_limited else None,
            'all_timestamps': [ts.isoformat() for ts in merged_limited],
            'cached_at': datetime.now(UTC).isoformat(),
            'last_event_type': last_event_type,
            'last_work_types': last_work_types,
            'last_operator_id': last_operator_id,
        }

        with open(CACHE_FILE, 'w') as f:
            json.dump(cache_payload, f, indent=2)

        return {
            'cached_at': datetime.fromisoformat(cache_payload['cached_at']),
            'all_timestamps': merged_limited,
            'last_plowing': merged_limited[0] if merged_limited else None,
            'last_event_type': last_event_type,
            'last_work_types': last_work_types,
            'last_operator_id': last_operator_id,
        }
    except Exception as e:
        logger.warning(f"Kunne ikke lagre cache: {e}")
        return existing_cache or {
            'cached_at': datetime.now(UTC),
            'all_timestamps': [],
            'last_plowing': None,
        }


def _dedupe_and_sort(timestamps: list[datetime]) -> list[datetime]:
    """Dedupliserer og sorterer tidsstempler synkende."""
    unique = {ts.isoformat(): ts for ts in timestamps if isinstance(ts, datetime)}
    return sorted(unique.values(), reverse=True)
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
