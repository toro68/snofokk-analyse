🔴 Kritisk

  - pytest/mypy/ruff cannot run because pip install fails: sandbox
    blocks outbound HTTPS to PyPI, so test tooling and runtime
    deps are missing. No automated suite has executed; results are
    unknown.
  - SnowdriftAnalyzer only inspects the latest row.
    Historical episodes like Feb 2024 (see tests/
    test_february_2024_snowdrift.py) drop to 🟢 as soon as wind
    eases, even if prior hours were 🔴. This yields false “safe”
    reports whenever data includes a tapering tail.
  - Wind-gust data path mismatch: StationConfig.CORE_ELEMENTS
    requests max(wind_speed_of_gust PT1H) but _fetch_observations
    renames it to wind_gust. The analyzer reads wind_gust, yet
    FrostClient.COLUMN_MAPPING points to 'wind_gust' while other
    modules (e.g., enhanced_weather) expect max_wind_gust. Need
    consistent naming and element requests, or gust-trigger logic
    silently never fires.
  - SlapsAnalyzer treats temps above 4 °C as “MEDIUM” risk, even when
    rain is zero; this contradicts AGENTS.md (“over 4 °C = bare regn,
    no slaps”). False warnings appear during plain rain events.
  - Dew-point logic for snow/rain classification uses <
    thresholds.dew_point_max where dew_point_max = 0.0. AGENTS.md
    requires “duggpunkt < 0°C → snø”, but code falls back to air
    temp <1 °C even when dew point is missing or NaN, leading to snow
    flags in +1 °C rain if dew point isn’t available. Need explicit
    precipitation data validation.

  🟡 Viktig

  - Config vs spec gaps:
      - Snøfokk critical wind direction threshold set to 135–225°,
        but AGENTS.md calls SE–S only (135–225) for 🔴 and all
        directions for 🟡; analyzer treats critical direction as
        binary without differentiating severity.
      - snow_depth_min_cm is 6 cm while spec states ≥3 cm for
        snøfokk.
      - Fresh-snow precipitation minimum is 0.3 mm/t, but AGENT spec
        flags “nedbør > 0” for snow detection; config may under-
        report light flurries.
  - SlipperyRoadAnalyzer short-circuits to LOW whenever
    _check_snow_increase detects ≥1 cm rise in 6 h. During freezing
    rain on top of fresh snow, this suppresses alerts, conflicting
    with “nysnø > 2 mm under 1 °C acts as strøing” but only when
    temps stay below 1 °C. Current code never inspects temperature
    before downgrading risk.
  - FrostClient forces timeresolutions=PT1H but AGENTS.md cites PT10M
    dew point and snow thickness. Not sampling 10-minute data misses
    rapid spikes and can undercount snow-increase thresholds.
  - Netatmo cache functions rely on st.cache_data. When Netatmo
    auth fails, errors are swallowed with only logger.warning. No UI
    surfaced reason; repeated failures spam logs.
  - Time filtering uses datetime.now(timezone.utc) directly. Local
    UI displays naive times (e.g., render_key_metrics), so plowing
    timestamps and frost data mix UTC with local (Europe/Oslo)
    without conversion; test_timezone_handling likely expects correct
    tz awareness.

  🟢 Mindre

  - Missing dependency guard: repo lacks tzlocal, yet multiple tests
    import it to convert tz-aware times. Document requirement or add
    to requirements.
  - PlowmanClient falls back to regex scraping but does not cache
    debugging for new elements.
  - SlapsAnalyzer uses temps.mean() to decide “temperature falling”.
    This weights all readings equally; a single warm outlier skews
    detection. Using last-vs-first per AGENT guidance (“synkende mot
  (e.g., multi-hour snowfokk aggregation or config alignment) once we
  can install dependencies and rerun tests.