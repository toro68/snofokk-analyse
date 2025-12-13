"""
Smøreguide basert på Swix sine temperatur- og fuktighetssoner.

Modulen analyserer siste tilgjengelige værdata og anbefaler
Swix-produkter som passer forholdene på Gullingen.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd


@dataclass
class WaxRecommendation:
    """Resultat fra smøreguiden."""

    headline: str
    swix_family: str
    swix_products: list[str]
    temp_band: str
    condition: str
    instructions: list[str]
    factors: list[str]
    confidence: float
    metrics: dict[str, float | None]


def generate_wax_recommendation(df: pd.DataFrame) -> WaxRecommendation | None:
    """Lag en smøreguide basert på siste værmålinger."""

    if df is None or df.empty:
        return None

    latest = df.iloc[-1]

    air_temp = _safe_float(latest, "air_temperature")
    surface_temp = _safe_float(latest, "surface_temperature")
    humidity = _safe_float(latest, "relative_humidity")
    dew_point = _safe_float(latest, "dew_point_temperature")
    snow_depth = _safe_float(latest, "surface_snow_thickness")

    effective_temp = surface_temp if surface_temp is not None else air_temp
    if effective_temp is None:
        return None

    recent_precip = _recent_mean(df, "precipitation_1h", window=3)
    new_snow_last_hours = _recent_increase(df, "surface_snow_thickness", lookback=6)

    freeze_thaw = (
        air_temp is not None
        and surface_temp is not None
        and air_temp > 0
        and surface_temp < 0
    )

    wet_snow = (effective_temp >= 0.5) or (recent_precip is not None and recent_precip >= 0.8)
    humid_snow = humidity is not None and humidity >= 85

    metrics = {
        "air_temperature": air_temp,
        "surface_temperature": surface_temp,
        "relative_humidity": humidity,
        "dew_point": dew_point,
        "precipitation_recent": recent_precip,
        "snow_depth": snow_depth,
    }

    confidence = _confidence_from_metrics(metrics.values())
    factors: list[str] = []

    if humidity is not None:
        factors.append(f"Luftfuktighet {humidity:.0f}%")
    if recent_precip is not None:
        factors.append(f"Siste 3t nedbør {recent_precip:.1f} mm/h")
    if snow_depth is not None:
        factors.append(f"Snødybde {snow_depth:.0f} cm")
    if new_snow_last_hours:
        factors.append("Nysnø siste 6 timer")

    if effective_temp <= -10:
        return WaxRecommendation(
            headline="Kald tørrsnø",
            swix_family="Hardvoks – grønn/blå sone",
            swix_products=["Swix V05 Polar", "Swix V20 Green"],
            temp_band="-25 til -10°C",
            condition="Tørr og kald snø",
            instructions=_hardwax_instructions("VG30", layers=3),
            factors=[f"Bakke/luft {effective_temp:.1f}°C", *factors],
            confidence=confidence,
            metrics=metrics,
        )

    if effective_temp <= -3:
        if humid_snow:
            return WaxRecommendation(
                headline="Kald og fuktig nysnø",
                swix_family="Hardvoks – VR blå",
                swix_products=["Swix VR30", "Swix VR40 Blue Extra"],
                temp_band="-8 til -2°C",
                condition="Fuktig/snøfokk med nye krystaller",
                instructions=_hardwax_instructions("VG35", layers=4),
                factors=[f"Bakke/luft {effective_temp:.1f}°C", "Høy fuktighet", *factors],
                confidence=confidence,
                metrics=metrics,
            )
        return WaxRecommendation(
            headline="Blå fører",
            swix_family="Hardvoks – V blå",
            swix_products=["Swix V30", "Swix V40 Blue Extra"],
            temp_band="-8 til -3°C",
            condition="Tørr, eldre snø",
            instructions=_hardwax_instructions("VG30", layers=3),
            factors=[f"Bakke/luft {effective_temp:.1f}°C", *factors],
            confidence=confidence,
            metrics=metrics,
        )

    if effective_temp < -1:
        if humid_snow or new_snow_last_hours:
            return WaxRecommendation(
                headline="Fuktig violett",
                swix_family="Hardvoks – VR fiolett",
                swix_products=["Swix VR45", "Swix VR50"],
                temp_band="-3 til -1°C",
                condition="Fersk snø nær null",
                instructions=_hardwax_instructions("VG35", layers=4),
                factors=[f"Bakke/luft {effective_temp:.1f}°C", "Fersk snø", *factors],
                confidence=confidence,
                metrics=metrics,
            )
        return WaxRecommendation(
            headline="Violett på gammel snø",
            swix_family="Hardvoks – V fiolett",
            swix_products=["Swix V45", "Swix V50"],
            temp_band="-3 til -1°C",
            condition="Gammel eller omdannet snø",
            instructions=_hardwax_instructions("VG30", layers=3),
            factors=[f"Bakke/luft {effective_temp:.1f}°C", *factors],
            confidence=confidence,
            metrics=metrics,
        )

    if effective_temp <= 1.0:
        if wet_snow or humid_snow:
            return WaxRecommendation(
                headline="Nullføre med fukt",
                swix_family="Klister + dekning",
                swix_products=["Swix KX40S Silver", "Swix VR50 som dekning"],
                temp_band="-1 til +1°C",
                condition="Våt/fuktig snø ved null",
                instructions=_klister_instructions(topcoat="VR50"),
                factors=[
                    f"Bakke/luft {effective_temp:.1f}°C",
                    "Fuktig snø",
                    *factors,
                ],
                confidence=confidence,
                metrics=metrics,
            )
        return WaxRecommendation(
            headline="Nullføre tørr",
            swix_family="Hardvoks – VR55N",
            swix_products=["Swix VR50", "Swix VR55N"],
            temp_band="-1 til +1°C",
            condition="Skare eller blandet føre",
            instructions=_hardwax_instructions("VG35", layers=4),
            factors=[f"Bakke/luft {effective_temp:.1f}°C", *factors],
            confidence=confidence,
            metrics=metrics,
        )

    # Warmer than +1°C → klistervalg
    if freeze_thaw:
        return WaxRecommendation(
            headline="Isklister",
            swix_family="Klister – is/skare",
            swix_products=["Swix KX30 Ice Klister", "Swix KB20 base"]
            if snow_depth and snow_depth > 0
            else ["Swix KX30 Ice Klister"],
            temp_band="-3 til +3°C",
            condition="Is og fast skare etter mildvær",
            instructions=_klister_instructions(topcoat=None),
            factors=[
                f"Luft {air_temp:.1f}°C" if air_temp is not None else "",
                f"Bakke {surface_temp:.1f}°C" if surface_temp is not None else "",
                "Fryse/tine-syklus",
                *factors,
            ],
            confidence=confidence,
            metrics=metrics,
        )

    if wet_snow and recent_precip is not None and recent_precip >= 1.0:
        return WaxRecommendation(
            headline="Våt vårsnø",
            swix_family="Klister – rød/gul",
            swix_products=["Swix KX65 Red Klister", "Swix K22 Universal"],
            temp_band="0 til +5°C",
            condition="Regn på snø eller tung slaps",
            instructions=_klister_instructions(topcoat=None),
            factors=[f"Bakke/luft {effective_temp:.1f}°C", "Mye nedbør", *factors],
            confidence=confidence,
            metrics=metrics,
        )

    return WaxRecommendation(
        headline="Varm grovkornet snø",
        swix_family="Klister – gul",
        swix_products=["Swix KX75 Yellow", "Swix K70"],
        temp_band="+3 til +8°C",
        condition="Vårslush og grovkornet snø",
        instructions=_klister_instructions(topcoat=None),
        factors=[f"Bakke/luft {effective_temp:.1f}°C", *factors],
        confidence=confidence,
        metrics=metrics,
    )


def _safe_float(series: pd.Series, key: str) -> float | None:
    value = series.get(key)
    if value is None or pd.isna(value):
        return None
    return float(value)


def _recent_mean(df: pd.DataFrame, column: str, window: int = 3) -> float | None:
    if column not in df.columns:
        return None
    tail = df[column].tail(window).dropna()
    if tail.empty:
        return None
    return float(tail.mean())


def _recent_increase(df: pd.DataFrame, column: str, lookback: int) -> bool:
    if column not in df.columns:
        return False
    subset = df[column].tail(lookback + 1).dropna()
    if subset.shape[0] < 2:
        return False
    return bool((subset.diff() > 0.5).any())


def _confidence_from_metrics(values: Iterable[float | None]) -> float:
    total = 0
    missing = 0
    for value in values:
        total += 1
        if value is None:
            missing += 1
    if total == 0:
        return 0.5
    base = 0.85
    penalty = 0.15 * missing
    return max(0.4, base - penalty)


def _hardwax_instructions(basewax: str, layers: int) -> list[str]:
    return [
        f"Legg et tynt lag {basewax} som grunnvoks og kork lett.",
        f"Påfør {layers} tynne lag av anbefalt Swix-voks.",
        "Kork mellom hvert lag for å hindre ising.",
    ]


def _klister_instructions(topcoat: str | None) -> list[str]:
    steps = [
        "Varm klisteret lett inn med varmluft og jevn ut med fingeren.",
        "La sålen avkjøles før eventuell dekning.",
    ]
    if topcoat:
        steps.append(f"Legg et tynt lag {topcoat} over klisteret for å redusere ising.")
    steps.append("Bruk skrape for å fjerne gammel klister før ny påføring.")
    return steps

