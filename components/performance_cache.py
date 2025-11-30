#!/usr/bin/env python3
"""
Performance cache system for Enhanced Streamlit App
TTL-based caching with progressive loading and error handling
"""

import time
from collections.abc import Callable
from datetime import datetime
from typing import Any

import streamlit as st


class DataCache:
    """TTL-basert cache system for værdata"""

    @staticmethod
    def get_cached_data(key: str, fetch_func: Callable, ttl_seconds: int = 300,
                       params: dict | None = None) -> Any:
        """
        Hent cachet data eller utfør ny henting hvis TTL er utløpt

        Args:
            key: Cache nøkkel
            fetch_func: Funksjon for å hente nye data
            ttl_seconds: TTL i sekunder
            params: Parametere til fetch_func

        Returns:
            Cachet eller nye data
        """
        if 'cache_store' not in st.session_state:
            st.session_state.cache_store = {}

        cache = st.session_state.cache_store
        current_time = time.time()

        # Sjekk om data finnes og er gyldig
        if key in cache:
            data, timestamp = cache[key]
            if current_time - timestamp < ttl_seconds:
                return data

        # Hent nye data
        try:
            if params:
                new_data = fetch_func(**params)
            else:
                new_data = fetch_func()

            # Lagre i cache
            cache[key] = (new_data, current_time)

            # Cleanup gamle entries
            DataCache._cleanup_cache()

            return new_data

        except Exception as e:
            # Returner cachet data hvis mulig, ellers raise error
            if key in cache:
                st.warning(f"Bruker cachet data pga feil: {e}")
                return cache[key][0]
            else:
                raise e

    @staticmethod
    def invalidate_cache(key_pattern: str = None):
        """
        Tøm cache helt eller deler av cache

        Args:
            key_pattern: Mønster for å matche keys (None = tøm alt)
        """
        if 'cache_store' not in st.session_state:
            return

        if key_pattern is None:
            st.session_state.cache_store = {}
        else:
            # Fjern keys som matcher mønster
            cache = st.session_state.cache_store
            keys_to_remove = [k for k in cache.keys() if key_pattern in k]
            for key in keys_to_remove:
                del cache[key]

    @staticmethod
    def get_cache_stats() -> dict[str, Any]:
        """Få cache statistikk"""
        if 'cache_store' not in st.session_state:
            return {
                'entries': 0,
                'newest_age': None,
                'oldest_age': None,
                'total_size': 0
            }

        cache = st.session_state.cache_store
        current_time = time.time()

        if not cache:
            return {
                'entries': 0,
                'newest_age': None,
                'oldest_age': None,
                'total_size': 0
            }

        ages = [current_time - timestamp for _, timestamp in cache.values()]

        return {
            'entries': len(cache),
            'newest_age': min(ages) if ages else None,
            'oldest_age': max(ages) if ages else None,
            'total_size': len(str(cache))
        }

    @staticmethod
    def _cleanup_cache(max_entries: int = 20):
        """Rydd opp i cache - fjern eldste entries"""
        if 'cache_store' not in st.session_state:
            return

        cache = st.session_state.cache_store

        if len(cache) <= max_entries:
            return

        # Sorter etter timestamp og fjern eldste
        sorted_items = sorted(cache.items(), key=lambda x: x[1][1], reverse=True)

        # Behold kun max_entries nyeste
        new_cache = dict(sorted_items[:max_entries])
        st.session_state.cache_store = new_cache


class ProgressiveLoader:
    """Progressive loading for store datasett"""

    @staticmethod
    def load_critical_data_first(data_sources: dict[str, Callable],
                                critical_keys: list) -> dict[str, Any]:
        """
        Last kritiske data først, deretter resten

        Args:
            data_sources: Dict med nøkkel -> fetch_func
            critical_keys: Liste med kritiske nøkler som skal lastes først

        Returns:
            Dict med lastede data
        """
        results = {}

        # Last kritiske data først
        for key in critical_keys:
            if key in data_sources:
                try:
                    with st.spinner(f"Laster {key}..."):
                        results[key] = data_sources[key]()
                except Exception as e:
                    st.error(f"Feil ved lasting av {key}: {e}")
                    results[key] = None

        # Last resten
        remaining_keys = set(data_sources.keys()) - set(critical_keys)
        for key in remaining_keys:
            try:
                with st.spinner(f"Laster {key}..."):
                    results[key] = data_sources[key]()
            except Exception as e:
                st.error(f"Feil ved lasting av {key}: {e}")
                results[key] = None

        return results

    @staticmethod
    def show_skeleton_loader(sections: list):
        """Vis skeleton loader mens data lastes"""
        placeholders = {}

        for section in sections:
            placeholders[section] = st.empty()
            with placeholders[section].container():
                st.write(f"⏳ Laster {section}...")
                st.progress(0.5)

        return placeholders


class ErrorHandler:
    """Robust error handling med fallback"""

    @staticmethod
    def with_fallback(primary_func: Callable, fallback_func: Callable = None,
                     default_value: Any = None) -> Any:
        """
        Utfør primær funksjon med fallback

        Args:
            primary_func: Hovedfunksjon
            fallback_func: Fallback funksjon
            default_value: Default verdi hvis alt feiler

        Returns:
            Resultat fra primary_func, fallback_func eller default_value
        """
        try:
            return primary_func()
        except Exception as e:
            st.warning(f"Primær funksjon feilet: {e}")

            if fallback_func:
                try:
                    st.info("Prøver fallback...")
                    return fallback_func()
                except Exception as e2:
                    st.error(f"Fallback feilet også: {e2}")

            if default_value is not None:
                st.info("Bruker default verdi")
                return default_value

            # Re-raise hvis ingen fallback
            raise e

    @staticmethod
    def safe_data_fetch(fetch_func: Callable, default_value: Any = None,
                       error_message: str = "Feil ved datahenting") -> Any:
        """
        Sikker datahenting med error handling

        Args:
            fetch_func: Funksjon for å hente data
            default_value: Default verdi ved feil
            error_message: Feilmelding å vise

        Returns:
            Data eller default_value
        """
        try:
            return fetch_func()
        except Exception as e:
            st.error(f"{error_message}: {e}")
            return default_value


# Hjelpefunksjoner for caching patterns
def cache_weather_data(fetch_func: Callable, station_id: str,
                      start_time: datetime, end_time: datetime,
                      ttl_seconds: int = 300) -> Any:
    """Cache wrapper for værdata"""
    key = f"weather_data_{station_id}_{start_time.isoformat()}_{end_time.isoformat()}"
    params = {
        'station_id': station_id,
        'start_time': start_time,
        'end_time': end_time
    }
    return DataCache.get_cached_data(key, fetch_func, ttl_seconds, params)


def cache_analysis_result(fetch_func: Callable, analysis_type: str,
                         data_hash: str, ttl_seconds: int = 600) -> Any:
    """Cache wrapper for analyse-resultater"""
    key = f"analysis_{analysis_type}_{data_hash}"
    return DataCache.get_cached_data(key, fetch_func, ttl_seconds)
