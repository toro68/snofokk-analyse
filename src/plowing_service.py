"""
Brøytingsdata-tjeneste.

Henter data fra vedlikeholds-API og gir informasjon om siste brøyting
for å justere varsler i appen.
"""

import json
import logging
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


def _parse_ts_utc(value: str) -> datetime:
    """Parse ISO timestamp string, ensuring UTC timezone."""
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def _maintenance_keywords() -> set[str]:
    # Norsk + engelsk (API kan variere mellom systemer)
    return {
        "brøyting",
        "broyting",
        "brøyte",
        "broyte",
        "snøbrøyting",
        "plog",
        "snobroyting",
        "tunbrøyting",
        "tunbroyting",
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
        "stro",
        "stroing",
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
        now_utc = datetime.now(UTC)
        now_local = now_utc.astimezone(local_time.tzinfo)
        diff = now_utc - self.last_plowing
        day_diff = (now_local.date() - local_time.date()).days
        cfg = settings.plowing_service

        if day_diff == 0:
            if diff.seconds < cfg.formatted_recent_seconds:
                return f"For {diff.seconds // 60} min siden"
            else:
                return f"I dag kl. {local_time.strftime('%H:%M')}"
        elif day_diff == 1:
            return f"I går kl. {local_time.strftime('%H:%M')}"
        elif day_diff < cfg.formatted_week_days:
            dag_navn = ["man", "tir", "ons", "tor", "fre", "lør", "søn"]
            return f"{dag_navn[local_time.weekday()]} {local_time.strftime('%d.%m kl. %H:%M')}"
        else:
            return local_time.strftime("%d.%m.%Y kl. %H:%M")


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
            live_has_metadata = bool(event.work_types or event.event_type or event.status)
            cache_has_metadata = bool(
                (cache_data.get('last_work_types') if cache_data else None)
                or (cache_data.get('last_event_type') if cache_data else None)
            )

            if newest_cached and new_timestamp < newest_cached:
                if live_has_metadata and not cache_has_metadata:
                    logger.info(
                        "Live vedlikeholdsdata (%s) erstatter nyere cache (%s) fordi cache mangler metadata",
                        new_timestamp.isoformat(),
                        newest_cached.isoformat(),
                    )
                else:
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
    except (RuntimeError, ValueError, TypeError, KeyError, OSError) as e:
        logger.warning("Feil ved henting fra vedlikeholds-API: %s", e)

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
        with open(CACHE_FILE, encoding='utf-8') as f:
            raw = json.load(f)

        cached_at = datetime.fromisoformat(raw['cached_at'])
        # Gammel cache kan mangle tidssone-info; sikre UTC.
        if cached_at.tzinfo is None:
            cached_at = cached_at.replace(tzinfo=UTC)
        stored_timestamps = [
            _parse_ts_utc(ts)
            for ts in raw.get('all_timestamps', [])
            if ts
        ]

        if raw.get('last_plowing'):
            # Bakoverkompatibilitet: gamle cache-filer kan ha last_plowing uten
            # at den er inkludert i all_timestamps. _dedupe_and_sort rydder opp.
            stored_timestamps.append(_parse_ts_utc(raw['last_plowing']))

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
        logger.warning("Cache-lesefeil: %s", e)
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

        # Skriv atomisk: temp-fil + replace for å unngå korrupt JSON ved avbrudd.
        tmp_path = CACHE_FILE.with_suffix('.tmp')
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(cache_payload, f, indent=2)
        tmp_path.replace(CACHE_FILE)

        return {
            'cached_at': datetime.fromisoformat(str(cache_payload['cached_at'])),
            'all_timestamps': merged_limited,
            'last_plowing': merged_limited[0] if merged_limited else None,
            'last_event_type': last_event_type,
            'last_work_types': last_work_types,
            'last_operator_id': last_operator_id,
        }
    except (OSError, TypeError, ValueError) as e:
        logger.warning("Kunne ikke lagre cache: %s", e)
        return existing_cache or {
            'cached_at': datetime.now(UTC),
            'all_timestamps': [],
            'last_plowing': None,
        }


def _dedupe_and_sort(timestamps: list[datetime]) -> list[datetime]:
    """Dedupliserer og sorterer tidsstempler synkende."""
    unique = {ts.isoformat(): ts for ts in timestamps if isinstance(ts, datetime)}
    return sorted(unique.values(), reverse=True)


# Hovedfunksjon for å teste modulen
if __name__ == "__main__":
    info = get_plowing_info()
    print(f"Siste brøyting: {info.formatted_time}")
    print(f"Timer siden: {info.hours_since:.1f}" if info.hours_since else "Ukjent")
    print(f"Er nylig: {info.is_recent}")
    print(f"Kilde: {info.source}")

    if info.all_timestamps:
        print(f"\nAlle tidsstempler ({len(info.all_timestamps)}):")
        for ts in info.all_timestamps[:5]:
            print(f"  {ts.isoformat()}")
