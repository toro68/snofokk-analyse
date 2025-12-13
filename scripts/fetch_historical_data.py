#!/usr/bin/env python3
"""
Hent historiske værdata fra Frost API og lagre som JSON.

Brukes for å:
1. Verifisere tilgjengelige elementer
2. Bygge dataset for ML-analyse
3. Backup av historiske data

Bruk:
    python scripts/fetch_historical_data.py --years 2023 2024 2025
    python scripts/fetch_historical_data.py --start 2024-01-01 --end 2024-12-31
"""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

# Legg til src i path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import settings
from src.frost_client import FrostAPIError, FrostClient


def fetch_year(client: FrostClient, year: int, output_dir: Path) -> dict:
    """
    Hent data for ett år.

    Args:
        client: FrostClient instans
        year: År å hente
        output_dir: Mappe for output

    Returns:
        Statistikk for året
    """
    print(f"\n📅 Henter data for {year}...")

    start = datetime(year, 1, 1, tzinfo=UTC)
    end = datetime(year, 12, 31, 23, 59, 59, tzinfo=UTC)

    # Begrens til i dag hvis fremtidig dato
    now = datetime.now(UTC)
    if end > now:
        end = now

    if start > now:
        print(f"  ⏭️ Hopper over {year} (fremtidig)")
        return {"year": year, "records": 0, "skipped": True}

    try:
        weather_data = client.fetch_period(start, end)

        if weather_data.is_empty:
            print(f"  ADVARSEL: Ingen data for {year}")
            return {"year": year, "records": 0, "no_data": True}

        # Lagre til JSON
        output_file = output_dir / f"weather_{year}.json"
        weather_data.to_json(str(output_file))

        print(f"  OK: Hentet {weather_data.record_count} målinger")
        print(f"  LAGRET: {output_file}")

        return {
            "year": year,
            "records": weather_data.record_count,
            "file": str(output_file),
            "columns": list(weather_data.df.columns)
        }

    except FrostAPIError as e:
        print(f"  FEIL for {year}: {e}")
        return {"year": year, "records": 0, "error": str(e)}


def fetch_elements(client: FrostClient) -> list[str]:
    """Hent og vis tilgjengelige elementer."""
    print("\nHenter tilgjengelige elementer...")

    elements = client.fetch_available_elements()

    if elements:
        print(f"  OK: Funnet {len(elements)} elementer:")
        for elem in sorted(elements)[:20]:
            print(f"     - {elem}")
        if len(elements) > 20:
            print(f"     ... og {len(elements) - 20} flere")
    else:
        print("  ADVARSEL: Kunne ikke hente elementer")

    return elements


def main():
    """Hovedfunksjon."""
    parser = argparse.ArgumentParser(
        description="Hent historiske værdata fra Frost API"
    )
    parser.add_argument(
        '--years',
        type=int,
        nargs='+',
        help='År å hente (f.eks. 2023 2024 2025)'
    )
    parser.add_argument(
        '--start',
        type=str,
        help='Startdato (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--end',
        type=str,
        help='Sluttdato (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='data',
        help='Output-mappe (default: data)'
    )
    parser.add_argument(
        '--elements-only',
        action='store_true',
        help='Bare vis tilgjengelige elementer'
    )

    args = parser.parse_args()

    print("=" * 60)
    print("🌤️  FROST API - Historisk datahenting")
    print("=" * 60)
    print(f"Stasjon: {settings.station.name} ({settings.station.station_id})")

    # Sjekk konfigurasjon
    valid, msg = settings.validate()
    if not valid:
        print(f"\nFEIL: {msg}")
        sys.exit(1)

    # Opprett output-mappe
    output_dir = Path(args.output)
    output_dir.mkdir(exist_ok=True)

    # Initialiser klient
    client = FrostClient()

    # Hent elementer
    elements = fetch_elements(client)

    if args.elements_only:
        # Lagre elementer til fil
        elements_file = output_dir / "available_elements.json"
        with open(elements_file, 'w') as f:
            json.dump({
                "station_id": settings.station.station_id,
                "fetched_at": datetime.now(UTC).isoformat(),
                "elements": elements
            }, f, indent=2)
        print(f"\nLAGRET: Elementer til {elements_file}")
        return

    # Bestem perioder å hente
    if args.years:
        years = args.years
    elif args.start and args.end:
        start_year = datetime.fromisoformat(args.start).year
        end_year = datetime.fromisoformat(args.end).year
        years = list(range(start_year, end_year + 1))
    else:
        # Default: siste 3 år
        current_year = datetime.now().year
        years = [current_year - 2, current_year - 1, current_year]

    print(f"\nHenter data for år: {years}")

    # Hent data
    results = []
    for year in years:
        result = fetch_year(client, year, output_dir)
        results.append(result)

    # Oppsummering
    print("\n" + "=" * 60)
    print("OPPSUMMERING")
    print("=" * 60)

    total_records = sum(r.get('records', 0) for r in results)
    successful = [r for r in results if r.get('records', 0) > 0]

    print(f"OK: Hentet {total_records} målinger fra {len(successful)} år")

    for r in results:
        status = "OK" if r.get('records', 0) > 0 else "FEIL"
        print(f"   {status} {r['year']}: {r.get('records', 0)} målinger")

    # Lagre sammendrag
    summary_file = output_dir / "fetch_summary.json"
    with open(summary_file, 'w') as f:
        json.dump({
            "fetched_at": datetime.now(UTC).isoformat(),
            "station_id": settings.station.station_id,
            "total_records": total_records,
            "years": results,
            "available_elements": elements
        }, f, indent=2)

    print(f"\nLAGRET: Sammendrag til {summary_file}")
    print("\nOK: Ferdig!")


if __name__ == "__main__":
    main()
