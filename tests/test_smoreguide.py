import pandas as pd

from src.components.smoreguide import generate_wax_recommendation


def test_smoreguide_does_not_jump_to_v55_on_humidity_only() -> None:
    """Høy luftfuktighet skal ikke kunne velge voks utenfor temp-intervallet.

    Regression: Ved ca -2.5°C og høy fuktighet kunne guiden hoppe fra V45 -> V55,
    selv om V55 (nysnø) er 0 til 1°C.
    """

    # 7 målinger (lookback=6) med tydelig nysnø-indikasjon (>0.5 cm økning)
    df = pd.DataFrame(
        {
            "air_temperature": [-2.4] * 7,
            "surface_temperature": [-2.5] * 7,
            "relative_humidity": [90.0] * 7,
            "precipitation_1h": [2.8] * 7,
            "surface_snow_thickness": [12.0, 12.2, 12.4, 12.6, 12.8, 13.2, 14.0],
        }
    )

    rec = generate_wax_recommendation(df)
    assert rec is not None

    assert not any("V55" in product for product in rec.swix_products)
    assert any("V45" in product for product in rec.swix_products)
    assert rec.metrics["surface_temperature"] == -2.5


def test_smoreguide_avoids_klister_in_marginal_dry_minus_conditions() -> None:
    """Skal ikke hoppe til klister kun fordi temp er nær -1°C."""
    df = pd.DataFrame(
        {
            "air_temperature": [-0.9] * 7,
            "surface_temperature": [-0.8] * 7,
            "relative_humidity": [65.0] * 7,
            "precipitation_1h": [0.0] * 7,
            "dew_point_temperature": [-2.0] * 7,
            "surface_snow_thickness": [18.0] * 7,  # omdannet/stabil snø
        }
    )

    rec = generate_wax_recommendation(df)
    assert rec is not None
    assert rec.swix_family == "Hardvoks (V-serien)"


def test_smoreguide_uses_klister_when_wet_and_transformed() -> None:
    """Vått omdannet føre skal gi klister."""
    df = pd.DataFrame(
        {
            "air_temperature": [1.0] * 7,
            "surface_temperature": [0.8] * 7,
            "relative_humidity": [90.0] * 7,
            "precipitation_1h": [1.2] * 7,
            "dew_point_temperature": [0.7] * 7,
            "surface_snow_thickness": [20.0] * 7,  # omdannet/stabil snø
        }
    )

    rec = generate_wax_recommendation(df)
    assert rec is not None
    assert rec.swix_family == "Klister (KX/K)"


def test_smoreguide_keeps_hardwax_on_strong_new_snow_signal_near_zero() -> None:
    """Sterk nysnøindikasjon skal favorisere hardvoks selv nær null."""
    df = pd.DataFrame(
        {
            "air_temperature": [-0.4] * 7,
            "surface_temperature": [-0.6] * 7,
            "relative_humidity": [88.0] * 7,
            "precipitation_1h": [0.6] * 7,
            "dew_point_temperature": [-0.2] * 7,
            "surface_snow_thickness": [10.0, 10.4, 10.8, 11.1, 11.5, 11.9, 12.3],
        }
    )

    rec = generate_wax_recommendation(df)
    assert rec is not None
    assert rec.swix_family == "Hardvoks (V-serien)"
