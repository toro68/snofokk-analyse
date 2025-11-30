#!/usr/bin/env python3
"""
Last ned historiske værdata fra Frost API (2018-2025) for lokal testing.
Bruker de 15 empirisk validerte værelementene fra Gullingen stasjon.
"""
import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

import aiohttp

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.snofokk.config import settings

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HistoricalWeatherDownloader:
    """Last ned historiske værdata for lokal testing"""

    def __init__(self):
        self.base_url = 'https://frost.met.no/observations/v0.jsonld'
        self.station_id = "SN46220"  # Gullingen
        self.data_dir = Path(__file__).parent.parent / "data" / "historical"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # De 15 empirisk validerte elementene fra forskningen
        self.validated_elements = [
            "sum(precipitation_amount PT1H)",           # Nedbør per time (mm)
            "wind_from_direction",                      # Vindretning (grader)
            "max(wind_speed PT1H)",                     # Maks vindstyrke per time
            "surface_snow_thickness",                   # Snødybde på bakken (cm)
            "surface_temperature",                      # Bakketemperatur (°C)
            "air_temperature",                          # Lufttemperatur (°C)
            "sum(precipitation_amount PT10M)",          # 10-min nedbør (mm)
            "dew_point_temperature",                    # Duggpunkt (°C)
            "relative_humidity",                        # Relativ fuktighet (%)
            "precipitation_duration(precipitation_amount PT1H)", # Nedbørvarighet per time
            "wind_speed",                               # Vindstyrke (m/s)
            "sum(precipitation_amount P1D)",            # Akkumulert nedbør (mm)
            "max(wind_speed_of_gust PT1H)",            # Vindkast per time (m/s)
            "max(air_temperature PT1H)",               # Maks lufttemp per time (°C)
            "min(air_temperature PT1H)"                # Min lufttemp per time (°C)
        ]

    async def download_year_data(self, year: int, session: aiohttp.ClientSession) -> dict:
        """Last ned data for ett år"""
        start_date = f"{year}-01-01T00:00:00Z"
        end_date = f"{year + 1}-01-01T00:00:00Z"

        logger.info(f"Laster ned data for {year}...")

        # Split elements into smaller groups to avoid API limits
        element_chunks = [
            self.validated_elements[i:i+5]
            for i in range(0, len(self.validated_elements), 5)
        ]

        all_data = {}

        for chunk_idx, elements in enumerate(element_chunks):
            logger.info(f"  Chunk {chunk_idx + 1}/{len(element_chunks)}: {elements[:2]}...")

            params = {
                'sources': self.station_id,
                'referencetime': f"{start_date}/{end_date}",
                'elements': ','.join(elements),
                'timeoffsets': 'PT0H',
                'timeresolutions': 'PT1H',
                'format': 'jsonld'
            }

            auth = aiohttp.BasicAuth(settings.frost_client_id, '')

            try:
                async with session.get(
                    self.base_url,
                    params=params,
                    auth=auth,
                    timeout=aiohttp.ClientTimeout(total=300)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        all_data[f"chunk_{chunk_idx}"] = data
                        logger.info(f"    ✓ Hentet {len(data.get('data', []))} observasjoner")
                    else:
                        logger.error(f"    ✗ API-feil {response.status}")
                        error_text = await response.text()
                        logger.error(f"    Error: {error_text[:200]}...")

            except TimeoutError:
                logger.error(f"    ✗ Timeout for chunk {chunk_idx}")
                continue
            except Exception as e:
                logger.error(f"    ✗ Feil: {e}")
                continue

            # Rate limiting
            await asyncio.sleep(1)

        return all_data

    def merge_and_save_year(self, year: int, raw_data: dict) -> bool:
        """Merge chunks og lagre årsdata"""
        if not raw_data:
            logger.warning(f"Ingen data for {year}")
            return False

        # Combine all observations from chunks
        all_observations = []
        for _chunk_key, chunk_data in raw_data.items():
            observations = chunk_data.get('data', [])
            all_observations.extend(observations)

        if not all_observations:
            logger.warning(f"Ingen observasjoner for {year}")
            return False

        # Create structured data
        structured_data = {
            "metadata": {
                "year": year,
                "station": self.station_id,
                "station_name": "Gullingen",
                "download_timestamp": datetime.now().isoformat(),
                "validated_elements": self.validated_elements,
                "total_observations": len(all_observations)
            },
            "observations": all_observations
        }

        # Save to file
        output_file = self.data_dir / f"gullingen_weather_{year}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(structured_data, f, indent=2, ensure_ascii=False)

        logger.info(f"✓ Lagret {len(all_observations)} observasjoner til {output_file}")
        return True

    async def download_all_years(self, start_year: int = 2018, end_year: int = 2025):
        """Last ned data for alle år"""
        logger.info(f"Starter nedlasting av værdata {start_year}-{end_year}")
        logger.info(f"Elementer: {len(self.validated_elements)} validerte værelementer")

        async with aiohttp.ClientSession() as session:
            for year in range(start_year, end_year + 1):
                try:
                    raw_data = await self.download_year_data(year, session)
                    success = self.merge_and_save_year(year, raw_data)

                    if success:
                        logger.info(f"✓ {year} fullført")
                    else:
                        logger.warning(f"⚠ {year} delvis mislykket")

                except Exception as e:
                    logger.error(f"✗ {year} feilet: {e}")

                # Break between years to be nice to API
                if year < end_year:
                    logger.info("Pause 3 sekunder...")
                    await asyncio.sleep(3)

        logger.info("✓ Nedlasting fullført!")

    def create_summary_file(self):
        """Lag sammendrag av nedlastede data"""
        summary = {
            "summary": {
                "created": datetime.now().isoformat(),
                "station": self.station_id,
                "station_name": "Gullingen",
                "purpose": "Historical weather data for local testing without API calls",
                "validated_elements": self.validated_elements,
                "element_count": len(self.validated_elements)
            },
            "files": []
        }

        for year_file in sorted(self.data_dir.glob("gullingen_weather_*.json")):
            try:
                with open(year_file, encoding='utf-8') as f:
                    data = json.load(f)

                file_info = {
                    "filename": year_file.name,
                    "year": data["metadata"]["year"],
                    "observation_count": data["metadata"]["total_observations"],
                    "file_size_kb": round(year_file.stat().st_size / 1024, 1)
                }
                summary["files"].append(file_info)

            except Exception as e:
                logger.warning(f"Kunne ikke lese {year_file}: {e}")

        summary_file = self.data_dir / "historical_weather_summary.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        logger.info(f"✓ Sammendrag lagret til {summary_file}")

        # Print summary
        print("\n" + "="*60)
        print("HISTORISKE VÆRDATA - SAMMENDRAG")
        print("="*60)
        print(f"Stasjon: {summary['summary']['station_name']} ({summary['summary']['station']})")
        print(f"Elementer: {summary['summary']['element_count']} validerte værelementer")
        print(f"Filer: {len(summary['files'])} årsfiler")

        total_obs = sum(f["observation_count"] for f in summary["files"])
        total_size = sum(f["file_size_kb"] for f in summary["files"])

        print(f"Total observasjoner: {total_obs:,}")
        print(f"Total størrelse: {total_size:.1f} KB")
        print("\nÅrlige filer:")
        for file_info in summary["files"]:
            print(f"  {file_info['year']}: {file_info['observation_count']:,} obs ({file_info['file_size_kb']} KB)")
        print("="*60)


async def main():
    """Main function"""
    print("HISTORISK VÆRDATA NEDLASTING")
    print("="*50)
    print("Laster ned validerte værelementer fra Gullingen stasjon")
    print("Periode: 2018-2025")
    print("Formål: Lokal testing uten API-kall")
    print("="*50)

    downloader = HistoricalWeatherDownloader()

    # Download all years
    await downloader.download_all_years(2018, 2025)

    # Create summary
    downloader.create_summary_file()

    print("\n✓ NEDLASTING FULLFØRT!")
    print(f"Data lagret i: {downloader.data_dir}")


if __name__ == "__main__":
    asyncio.run(main())
