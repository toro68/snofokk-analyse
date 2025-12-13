import logging

import numpy as np
import pandas as pd

from src.config import settings

class PrecipitationTypeAnalyzer:
    """Analyserer type og intensitet av nedbør"""

    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.logger = logging.getLogger(self.__class__.__name__)

        # Påkrevde kolonner
        self.required_columns = {
            "temperature": "air_temperature",
            "precipitation": "sum(precipitation_amount PT1H)",
            "humidity": "relative_humidity",
            "dew_point": "dew_point_temperature",
        }

        self.validate_data()

    def validate_data(self) -> None:
        """Validerer at nødvendige kolonner eksisterer"""
        missing = set(self.required_columns.values()) - set(self.df.columns)
        if missing:
            raise ValueError(f"Mangler påkrevde kolonner: {missing}")

    def analyze(self) -> pd.DataFrame:
        """Hovedanalyse av nedbørstype og intensitet"""
        results = self.df.copy()

        # Klassifiser nedbør
        results["precip_type"] = self._classify_precipitation_type()
        results["precip_intensity"] = self._classify_intensity()

        # Beregn sannsynligheter
        probs = self._calculate_probabilities()
        results["snow_prob"] = probs["snow"]
        results["rain_prob"] = probs["rain"]
        results["mixed_prob"] = probs["mixed"]

        # Beregn risiko for overgang mellom typer
        results["transition_risk"] = self._calculate_transition_risk()

        return results

    def _classify_precipitation_type(self) -> pd.Series:
        """Klassifiserer nedbørstype basert på temperatur og duggpunkt"""
        th = settings.scripts
        temp = self.df[self.required_columns["temperature"]]
        precip = self.df[self.required_columns["precipitation"]]

        # Kun klassifiser når det faktisk er nedbør
        pd.Series("none", index=self.df.index)
        has_precip = precip >= settings.fresh_snow.precipitation_min

        conditions = [
            (temp <= th.precip_type_temp_snow_c) & has_precip,
            (temp > th.precip_type_temp_mix_low_c)
            & (temp <= th.precip_type_temp_mix_high_c)
            & has_precip,
            (temp > th.precip_type_temp_mix_high_c) & has_precip,
        ]
        choices = ["snow", "mixed", "rain"]

        return pd.Series(
            np.select(conditions, choices, default="none"), index=self.df.index
        )

    def _classify_intensity(self) -> pd.Series:
        """Klassifiserer nedbørintensitet"""
        th = settings.scripts
        precip = self.df[self.required_columns["precipitation"]]

        conditions = [
            (precip > th.precip_intensity_heavy_mmph),
            (precip > th.precip_intensity_moderate_mmph),
            (precip > th.precip_intensity_light_mmph),
            (precip >= settings.fresh_snow.precipitation_min),
        ]
        choices = ["heavy", "moderate", "light", "trace"]

        return pd.Series(
            np.select(conditions, choices, default="none"), index=self.df.index
        )

    def _calculate_probabilities(self) -> dict[str, pd.Series]:
        """Beregner sannsynlighet for hver nedbørstype"""
        th = settings.scripts
        temp = self.df[self.required_columns["temperature"]]
        humidity = self.df[self.required_columns["humidity"]]

        # Temperaturbaserte sannsynligheter
        coef = th.precip_probability_temp_coef
        snow_prob = 1 - (1 / (1 + np.exp(-coef * (temp + th.precip_probability_snow_temp_offset_c))))
        rain_prob = 1 / (1 + np.exp(-coef * (temp - th.precip_probability_rain_temp_offset_c)))
        mixed_prob = 1 - (snow_prob + rain_prob)

        # Juster med luftfuktighet
        humidity_factor = humidity / 100

        return {
            "snow": snow_prob * humidity_factor,
            "rain": rain_prob * humidity_factor,
            "mixed": mixed_prob * humidity_factor,
        }

    def _calculate_transition_risk(self) -> pd.Series:
        """Beregner risiko for overgang mellom nedbørstyper"""
        th = settings.scripts
        temp = self.df[self.required_columns["temperature"]]

        # Beregn temperaturendring
        temp_change = temp.diff().abs()

        # Høyere risiko når temperaturen er nær grenseverdiene
        near_threshold = (abs(temp - th.precip_type_temp_snow_c) < th.precip_transition_near_threshold_delta_c) | (
            abs(temp - th.precip_type_temp_mix_high_c) < th.precip_transition_near_threshold_delta_c
        )

        # Kombiner faktorer
        transition_risk = pd.Series(0.0, index=self.df.index)
        transition_risk[near_threshold] += th.precip_transition_near_threshold_base_risk
        transition_risk += temp_change * th.precip_transition_temp_change_weight

        return transition_risk.clip(0, 1)
