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
