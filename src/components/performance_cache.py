"""
Avansert caching system for bedre ytelse på mobil
Implementerer TTL-basert caching og progressive loading
"""
import hashlib
import time
from collections.abc import Callable
from typing import Any

import pandas as pd
import streamlit as st

from src.config import settings


class DataCache:
    """Avansert data caching med TTL og kompresjon"""

    @staticmethod
    def _generate_cache_key(base_key: str, params: dict[str, Any]) -> str:
        """Generer unik cache-nøkkel basert på parametere"""
        param_str = str(sorted(params.items()))
        hash_obj = hashlib.md5(param_str.encode())
        return f"{base_key}_{hash_obj.hexdigest()[:8]}"

    @staticmethod
    def get_cached_data(
        key: str,
        fetch_func: Callable,
        ttl_seconds: int = 300,
        params: dict[str, Any] | None = None
    ) -> Any:
        """
        Hent cached data eller oppdater hvis utløpt

        Args:
            key: Base cache key
            fetch_func: Funksjon for å hente nye data
            ttl_seconds: Time to live i sekunder
            params: Parametere for cache key generering
        """
        if params is None:
            params = {}

        cache_key = DataCache._generate_cache_key(key, params)

        # Initialiser cache hvis den ikke eksisterer
        if 'data_cache' not in st.session_state:
            st.session_state.data_cache = {}

        cache = st.session_state.data_cache
        now = time.time()

        # Sjekk om data eksisterer og er gyldig
        if cache_key in cache:
            cached_item = cache[cache_key]
            age = now - cached_item['timestamp']

            if age < ttl_seconds:
                return cached_item['data']

        # Hent nye data
        try:
            fresh_data = fetch_func()
            cache[cache_key] = {
                'data': fresh_data,
                'timestamp': now,
                'ttl': ttl_seconds
            }

            # Rydd opp gamle cache-oppføringer
            DataCache._cleanup_cache()

            return fresh_data

        except Exception as e:
            # Returner gamle data hvis tilgjengelig ved feil
            if cache_key in cache:
                st.warning(f"Bruker cached data pga. feil: {str(e)[:50]}...")
                return cache[cache_key]['data']
            raise

    @staticmethod
    def _cleanup_cache():
        """Fjern utløpte cache-oppføringer"""
        if 'data_cache' not in st.session_state:
            return

        cache = st.session_state.data_cache
        now = time.time()

        # Finn utløpte nøkler
        expired_keys = []
        cache_cfg = settings.performance_cache
        for key, item in cache.items():
            age = now - item['timestamp']
            if age > item['ttl'] * cache_cfg.ttl_fallback_multiplier:  # Behold lengre for fallback
                expired_keys.append(key)

        # Fjern utløpte oppføringer
        for key in expired_keys:
            del cache[key]

        # Begrens cache størrelse
        if len(cache) > cache_cfg.max_entries:
            # Fjern eldste oppføringer
            sorted_items = sorted(cache.items(), key=lambda x: x[1]['timestamp'])
            keep_newest = min(cache_cfg.keep_newest_entries, cache_cfg.max_entries)
            for key, _ in sorted_items[:-keep_newest]:
                del cache[key]

    @staticmethod
    def invalidate_cache(key_pattern: str | None = None):
        """Fjern cache oppføringer"""
        if 'data_cache' not in st.session_state:
            return

        cache = st.session_state.data_cache

        if key_pattern is None:
            # Fjern all cache
            cache.clear()
        else:
            # Fjern spesifikke mønstre
            keys_to_remove = [k for k in cache.keys() if key_pattern in k]
            for key in keys_to_remove:
                del cache[key]

    @staticmethod
    def get_cache_stats() -> dict[str, Any]:
        """Hent cache statistikk"""
        if 'data_cache' not in st.session_state:
            return {'entries': 0, 'total_size': 0, 'oldest': None, 'newest': None}

        cache = st.session_state.data_cache
        now = time.time()

        if not cache:
            return {'entries': 0, 'total_size': 0, 'oldest': None, 'newest': None}

        timestamps = [item['timestamp'] for item in cache.values()]

        return {
            'entries': len(cache),
            'total_size': sum(len(str(item['data'])) for item in cache.values()),
            'oldest': min(timestamps) if timestamps else None,
            'newest': max(timestamps) if timestamps else None,
            'oldest_age': (now - min(timestamps)) if timestamps else 0,
            'newest_age': (now - max(timestamps)) if timestamps else 0
        }


class ProgressiveLoader:
    """Progressive loading for bedre brukeropplevelse"""

    @staticmethod
    def load_critical_data_first(weather_data_func: Callable) -> dict[str, Any]:
        """
        Last kritiske data først, deretter detaljer

        Returns:
            Dict med 'critical' og 'detailed' data
        """
        result = {
            'critical': None,
            'detailed': None,
            'loading_detailed': False
        }

        # Steg 1: Last kritiske data umiddelbart
        try:
            # Bruk cached critical data (kortere TTL)
            critical_data = DataCache.get_cached_data(
                'critical_weather',
                lambda: weather_data_func(hours_back=3),  # Bare siste 3 timer for kritisk
                ttl_seconds=60,  # 1 minutt TTL for kritisk data
                params={'type': 'critical', 'hours': 3}
            )
            result['critical'] = critical_data

        except Exception as e:
            st.error(f"Kunne ikke laste kritiske data: {e}")
            return result

        # Steg 2: Last detaljerte data i bakgrunnen
        if st.session_state.get('load_detailed', True):
            result['loading_detailed'] = True
            try:
                detailed_data = DataCache.get_cached_data(
                    'detailed_weather',
                    lambda: weather_data_func(hours_back=24),  # Full dataset
                    ttl_seconds=300,  # 5 minutter TTL for detaljert data
                    params={'type': 'detailed', 'hours': 24}
                )
                result['detailed'] = detailed_data
                result['loading_detailed'] = False

            except Exception as e:
                st.warning(f"Kunne ikke laste detaljerte data: {e}")
                result['loading_detailed'] = False

        return result

    @staticmethod
    def show_skeleton_loader(content_type: str = "card"):
        """Vis skeleton loader mens data lastes"""

        if content_type == "card":
            st.markdown("""
            <div class="skeleton-container">
                <div class="skeleton skeleton-card"></div>
                <div class="skeleton skeleton-text"></div>
                <div class="skeleton skeleton-text" style="width: 60%"></div>
            </div>

            <style>
            @keyframes shimmer {
                0% { background-position: -200% 0; }
                100% { background-position: 200% 0; }
            }

            .skeleton {
                background: linear-gradient(90deg,
                    #f0f0f0 25%,
                    #e0e0e0 50%,
                    #f0f0f0 75%);
                background-size: 200% 100%;
                animation: shimmer 1.5s infinite;
                border-radius: 8px;
            }

            .skeleton-card {
                height: 120px;
                margin: 10px 0;
                border-radius: 12px;
            }

            .skeleton-text {
                height: 20px;
                margin: 10px 0;
                width: 80%;
            }

            .skeleton-container {
                margin-bottom: 1rem;
            }
            </style>
            """, unsafe_allow_html=True)

        elif content_type == "chart":
            st.markdown("""
            <div class="skeleton skeleton-chart"></div>

            <style>
            .skeleton-chart {
                height: 300px;
                margin: 10px 0;
                border-radius: 8px;
                background: linear-gradient(90deg,
                    #f0f0f0 25%,
                    #e0e0e0 50%,
                    #f0f0f0 75%);
                background-size: 200% 100%;
                animation: shimmer 1.5s infinite;
            }
            </style>
            """, unsafe_allow_html=True)

        elif content_type == "metrics":
            st.markdown("""
            <div class="metrics-skeleton">
                <div class="skeleton skeleton-metric"></div>
                <div class="skeleton skeleton-metric"></div>
                <div class="skeleton skeleton-metric"></div>
                <div class="skeleton skeleton-metric"></div>
            </div>

            <style>
            .metrics-skeleton {
                display: grid;
                grid-template-columns: repeat(4, 1fr);
                gap: 0.5rem;
                margin: 1rem 0;
            }

            .skeleton-metric {
                height: 80px;
                border-radius: 8px;
                background: linear-gradient(90deg,
                    #f0f0f0 25%,
                    #e0e0e0 50%,
                    #f0f0f0 75%);
                background-size: 200% 100%;
                animation: shimmer 1.5s infinite;
            }

            @media (max-width: 768px) {
                .metrics-skeleton {
                    grid-template-columns: repeat(2, 1fr);
                }
            }
            </style>
            """, unsafe_allow_html=True)


class ErrorHandler:
    """Robust error handling med fallbacks"""

    @staticmethod
    def with_fallback(
        primary_func: Callable,
        fallback_func: Callable | None = None,
        error_message: str = "En feil oppstod"
    ) -> Any:
        """
        Kjør en funksjon med fallback ved feil

        Args:
            primary_func: Primær funksjon å kjøre
            fallback_func: Fallback funksjon ved feil
            error_message: Feilmelding å vise
        """
        try:
            return primary_func()

        except Exception as e:
            # Log feilen
            error_details = f"{error_message}: {str(e)}"

            # Prøv fallback
            if fallback_func:
                try:
                    st.warning(f"{error_message} - bruker backup data")
                    return fallback_func()
                except Exception as fallback_error:
                    st.error(f"Både primær og backup feilet: {fallback_error}")
                    return None
            else:
                st.error(error_details)
                return None

    @staticmethod
    def safe_data_fetch(fetch_func: Callable, default_value: Any = None) -> Any:
        """Sikker data-henting med standardverdi"""
        return ErrorHandler.with_fallback(
            primary_func=fetch_func,
            fallback_func=lambda: default_value,
            error_message="Kunne ikke hente data"
        )


# Utility functions for common patterns
def cached_weather_fetch(client_id: str, station_id: str, hours: int = 24) -> pd.DataFrame:
    """Cached værdata henting"""

    def fetch_weather():
        # Import her for å unngå sirkulære imports
        from weather_utils import fetch_frost_data
        return fetch_frost_data(client_id, station_id, hours)

    return DataCache.get_cached_data(
        'weather_data',
        fetch_weather,
        ttl_seconds=300,  # 5 minutter
        params={'station': station_id, 'hours': hours}
    )


def progressive_weather_load(client_id: str, station_id: str) -> dict[str, Any]:
    """Progressive weather loading med error handling"""

    def fetch_func(hours_back):
        # Import her for å unngå sirkulære imports
        from weather_utils import fetch_frost_data
        return fetch_frost_data(client_id, station_id, hours_back)

    return ProgressiveLoader.load_critical_data_first(fetch_func)
