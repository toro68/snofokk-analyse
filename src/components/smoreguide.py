"""
Smøreguide basert på Swix sine temperatur- og fuktighetssoner.

Modulen analyserer siste tilgjengelige værdata og anbefaler
Swix-produkter som passer forholdene på Gullingen.

Kilder og datagrunnlag (som lagt inn i koden her):
- Swix V-serien hardvoks: produktspesifikasjoner (to temperaturintervaller per voks: nysnø vs omdannet snø)
- Swix KX-serien klister: temperaturintervaller for klister
- Swix Wax Manual/"Grip Tip" og Swix School: tommelfingerregler for luftfuktighet og snøtransformasjon

Merk om verifisering:
- Denne modulen har ikke tilgang til eksterne PDF-er. Tallene under må derfor betraktes som
    "datagrunnlag slik det er lagt inn i kode" og bør sammenlignes mot dine kildedokumenter ved behov.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd


@dataclass(frozen=True)
class _TempBand:
    min_c: float
    max_c: float

    def contains(self, temp_c: float) -> bool:
        return self.min_c <= temp_c <= self.max_c

    def midpoint(self) -> float:
        return (self.min_c + self.max_c) / 2.0


@dataclass(frozen=True)
class _WaxSpec:
    code: str
    name: str
    new_snow: _TempBand
    transformed: _TempBand
    comment: str = ""


@dataclass(frozen=True)
class _KlisterSpec:
    code: str
    name: str
    temp: _TempBand
    use_case: str = ""


def get_sources_section_markdown() -> str:
    """Returner en kort kildeseksjon for visning i UI."""

    return (
        "**Kilder og datagrunnlag**\n"
        "- Swix V-serien hardvoks: produktspesifikasjoner (to temp-intervaller per voks: nysnø vs omdannet snø)\n"
        "- Swix KX-serien klister: temperaturintervaller for klister\n"
        "- Swix Wax Manual / \"Grip Tip\" og Swix School: tommelfingerregler for luftfuktighet og snøtransformasjon\n\n"
        "**Bekreftelse av data**\n"
        "Tallene som brukes av smøreguiden er lagt inn i koden som temperaturintervaller per voks/klister. "
        "Hvis du ønsker 100% samsvar med en spesifikk PDF-utgave, sammenlign intervallene under mot dokumentet du har."  # noqa: E501
    )


# V-serien hardvoks (temperaturintervaller) – lagt inn basert på tallene du oppga.
_V_SERIES: list[_WaxSpec] = [
    _WaxSpec(
        code="V20",
        name="Grønn",
        new_snow=_TempBand(min_c=-20.0, max_c=-10.0),
        transformed=_TempBand(min_c=-15.0, max_c=-8.0),
        comment="For svært kaldt vær. Høy slitestyrke.",
    ),
    _WaxSpec(
        code="V30",
        name="Blå",
        new_snow=_TempBand(min_c=-10.0, max_c=-2.0),
        transformed=_TempBand(min_c=-15.0, max_c=-5.0),
        comment="Standardvoks for minusgrader.",
    ),
    _WaxSpec(
        code="V40",
        name="Blå Extra",
        new_snow=_TempBand(min_c=-7.0, max_c=-1.0),
        transformed=_TempBand(min_c=-10.0, max_c=-3.0),
        comment="Dekker mye av normalt vinterføre.",
    ),
    _WaxSpec(
        code="V45",
        name="Fiolett",
        new_snow=_TempBand(min_c=-3.0, max_c=0.0),
        transformed=_TempBand(min_c=-6.0, max_c=-2.0),
        comment="Brukes når blå extra er for hard.",
    ),
    _WaxSpec(
        code="V55",
        name="Rød Spesial",
        new_snow=_TempBand(min_c=0.0, max_c=1.0),
        transformed=_TempBand(min_c=-2.0, max_c=0.0),
        comment="For fuktig nysnø. Krever forsiktighet for å unngå ising.",
    ),
    _WaxSpec(
        code="V60",
        name="Rød/Sølv",
        new_snow=_TempBand(min_c=0.0, max_c=3.0),
        transformed=_TempBand(min_c=-1.0, max_c=1.0),
        comment="For svært våt nysnø. Aluminium for å hindre ising.",
    ),
]


# KX-serien klister (temperaturintervaller) – lagt inn basert på tallene du oppga.
_KX_SERIES: list[_KlisterSpec] = [
    _KlisterSpec(
        code="KX30",
        name="Blå Isklister",
        temp=_TempBand(min_c=-12.0, max_c=0.0),
        use_case="Is og hardt skareføre.",
    ),
    _KlisterSpec(
        code="KX35",
        name="Fiolett Spesial",
        temp=_TempBand(min_c=-4.0, max_c=1.0),
        use_case="Frossen grovkornet snø.",
    ),
    _KlisterSpec(
        code="KX40S",
        name="Sølv",
        temp=_TempBand(min_c=-4.0, max_c=2.0),
        use_case="Omdannet finkornet snø. God når føret skifter.",
    ),
    _KlisterSpec(
        code="K22",
        name="Universal",
        temp=_TempBand(min_c=-3.0, max_c=10.0),
        use_case="Grovkornet snø. Dekker mye av gammelt føre.",
    ),
    _KlisterSpec(
        code="KX65",
        name="Rød",
        temp=_TempBand(min_c=1.0, max_c=5.0),
        use_case="Våt grovkornet snø.",
    ),
]


def _select_v_series(temp_c: float, *, snow_is_new: bool, humidity_pct: float | None) -> _WaxSpec:
    """Velg voks fra V-serien basert på temp + snøtype, med enkel fuktighetskorreksjon."""

    def band_for(wax: _WaxSpec) -> _TempBand:
        return wax.new_snow if snow_is_new else wax.transformed

    def clamp_not_warmer_than_temp(wax: _WaxSpec) -> _WaxSpec:
        """Sikkerhetsregel: anbefal aldri voks som er "varmere" enn faktisk temperatur.

        Tolkning: Hvis voksens nedre grense er høyere enn faktisk temp (f.eks. V55 (0–1°C) ved -2.4°C),
        så flytt ett hakk kaldere til vi er innenfor.
        """

        band = band_for(wax)
        if band.min_c <= temp_c:
            return wax

        ordered = _V_SERIES  # kald -> varm
        idx = ordered.index(wax)
        while idx > 0:
            idx -= 1
            candidate = ordered[idx]
            if band_for(candidate).min_c <= temp_c:
                return candidate
        return ordered[0]

    candidates: list[_WaxSpec] = []
    for wax in _V_SERIES:
        band = band_for(wax)
        if band.contains(temp_c):
            candidates.append(wax)

    # Fallback hvis temp faller utenfor alle intervaller: bruk nærmeste voks.
    if not candidates:
        def dist(w: _WaxSpec) -> float:
            band = band_for(w)
            if temp_c < band.min_c:
                return band.min_c - temp_c
            if temp_c > band.max_c:
                return temp_c - band.max_c
            return 0.0

        return clamp_not_warmer_than_temp(min(_V_SERIES, key=dist))

    # Velg voks hvis midtpunkt er nærmest temperaturen.
    def midpoint_dist(w: _WaxSpec) -> float:
        band = band_for(w)
        return abs(temp_c - band.midpoint())

    candidates = sorted(candidates, key=midpoint_dist)
    base = candidates[0]

    # Swix-regel (forenklet): høy fuktighet -> ett hakk mykere/varmere. Lav fuktighet -> ett hakk kaldere.
    if humidity_pct is None:
        return base

    humidity_step = 0
    if humidity_pct > 80.0:
        humidity_step = 1
    elif humidity_pct < 50.0:
        humidity_step = -1

    if humidity_step == 0:
        return clamp_not_warmer_than_temp(base)

    # Viktig: Fuktighetsjustering må aldri flytte oss til en voks som ikke
    # faktisk matcher temperaturen (ellers kan vi anbefale altfor varm voks
    # ved minusgrader, f.eks. V55 ved -2.5°C).
    def band_midpoint(w: _WaxSpec) -> float:
        band = band_for(w)
        return band.midpoint()

    ordered_candidates = sorted(candidates, key=band_midpoint)  # kald -> varm, men kun gyldige
    base_index = ordered_candidates.index(base)
    target_index = max(0, min(len(ordered_candidates) - 1, base_index + humidity_step))
    return clamp_not_warmer_than_temp(ordered_candidates[target_index])


def _select_klister(temp_c: float) -> _KlisterSpec:
    """Velg klister basert på temperatur."""

    candidates = [k for k in _KX_SERIES if k.temp.contains(temp_c)]
    if not candidates:
        # Fallback til nærmeste
        def dist(k: _KlisterSpec) -> float:
            if temp_c < k.temp.min_c:
                return k.temp.min_c - temp_c
            if temp_c > k.temp.max_c:
                return temp_c - k.temp.max_c
            return 0.0

        return min(_KX_SERIES, key=dist)

    # Nærmeste midtpunkt
    return min(candidates, key=lambda k: abs(temp_c - k.temp.midpoint()))


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

    # Bruk siste rad som faktisk har temperaturdata. I praksis kan siste måling
    # mangle både luft- og bakketemperatur (og noen ganger kun ha min/max), og da
    # skal ikke hele smøreguiden "forsvinne".
    latest = None
    for _, row in df.iloc[::-1].iterrows():
        air_temp_candidate = _safe_float(row, "air_temperature")
        surface_temp_candidate = _safe_float(row, "surface_temperature")
        temp_min_candidate = _safe_float(row, "temp_min_1h")
        temp_max_candidate = _safe_float(row, "temp_max_1h")

        has_any_temp = any(
            x is not None
            for x in (air_temp_candidate, surface_temp_candidate, temp_min_candidate, temp_max_candidate)
        )
        if has_any_temp:
            latest = row
            break

    if latest is None:
        return None

    air_temp = _safe_float(latest, "air_temperature")
    surface_temp = _safe_float(latest, "surface_temperature")
    temp_min_1h = _safe_float(latest, "temp_min_1h")
    temp_max_1h = _safe_float(latest, "temp_max_1h")
    humidity = _safe_float(latest, "relative_humidity")
    dew_point = _safe_float(latest, "dew_point_temperature")
    snow_depth = _safe_float(latest, "surface_snow_thickness")

    # Fallback: hvis lufttemp mangler, forsøk å estimere fra min/max siste time.
    if air_temp is None:
        if temp_min_1h is not None and temp_max_1h is not None:
            air_temp = (temp_min_1h + temp_max_1h) / 2.0
        elif temp_min_1h is not None:
            air_temp = temp_min_1h
        elif temp_max_1h is not None:
            air_temp = temp_max_1h

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

    snow_is_new = bool(new_snow_last_hours)

    wet_snow = (
        (effective_temp >= 0.5)
        or (recent_precip is not None and recent_precip >= 0.8)
        or (dew_point is not None and dew_point > 0.0)
    )

    metrics = {
        "air_temperature": air_temp,
        "surface_temperature": surface_temp,
        "temp_min_1h": temp_min_1h,
        "temp_max_1h": temp_max_1h,
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
    if snow_is_new:
        factors.append("Nysnø (indikasjon: økning siste timer)")
    else:
        factors.append("Omdannet/gammel snø (ingen tydelig nysnø-økning)")

    # Forenklet tommelfingerregel: klister når snøen er omdannet og forholdene er fuktige/nær null.
    use_klister = (not snow_is_new) and (wet_snow or effective_temp >= -1.0 or freeze_thaw)

    if use_klister:
        klister = _select_klister(effective_temp)
        headline = "Klister" if not freeze_thaw else "Is/skare-klister"
        swix_family = "Klister (KX/K)"
        products = [f"Swix {klister.code} {klister.name}"]
        condition = klister.use_case or "Klisterføre"
        return WaxRecommendation(
            headline=headline,
            swix_family=swix_family,
            swix_products=products,
            temp_band=f"{klister.temp.min_c:g} til {klister.temp.max_c:g}°C",
            condition=condition,
            instructions=_klister_instructions(topcoat=None),
            factors=[f"Bakke/luft {effective_temp:.1f}°C", *factors],
            confidence=confidence,
            metrics=metrics,
        )

    wax = _select_v_series(effective_temp, snow_is_new=snow_is_new, humidity_pct=humidity)
    band = wax.new_snow if snow_is_new else wax.transformed
    snow_type_label = "nysnø" if snow_is_new else "omdannet snø"
    headline = f"Hardvoks {wax.code}"
    return WaxRecommendation(
        headline=headline,
        swix_family="Hardvoks (V-serien)",
        swix_products=[f"Swix {wax.code} {wax.name}"],
        temp_band=f"{band.min_c:g} til {band.max_c:g}°C",
        condition=f"Valgt ut fra {snow_type_label} + luftfuktighet",
        instructions=_hardwax_instructions("VG30", layers=3),
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
