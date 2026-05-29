"""Lighting Technology Adjustment (LTA) module.

Three confounds in VIIRS radiance that are NOT economic activity:

1. LED Spectral Shift: India's SLNP (Street Lighting National Programme)
   replaced sodium vapour lamps with white LEDs. White LEDs appear ~0.5–0.7×
   as bright to VIIRS per watt vs sodium because the sensor peaks in the
   orange band where sodium glows strongly. An LED replacement makes a growing
   city *appear to stagnate or dim* from space.

2. Rural Electrification Jumps: One-time radiance spikes when a region
   transitions from diesel/off-grid to grid power (e.g. Leh +138% in 2017
   after the 220kV Srinagar–Leh transmission line). These are real
   electrification events, not GDP growth.

3. Energy-Efficiency Dampening: Same economic activity uses fewer watts over
   time as efficiency standards tighten. Uncorrected, this makes GDP growth
   look slower than it really is.

References:
  Elvidge et al. (2017) "VIIRS Night-time Lights" — spectral response.
  India SLNP Annual Reports (MoP) — LED penetration by state.
  CEEW (2021) "Rural Electrification in India" — Saubhagya scheme data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from .utils import interpolate_population

# ---------------------------------------------------------------------------
# Spectral correction constants
# ---------------------------------------------------------------------------

# VIIRS-detected radiance per lumen: LED vs sodium vapour.
# LED produces ~0.55 the VIIRS signal of sodium for equal luminous output.
# Range from literature: 0.50–0.70. Default = 0.55 (conservative mid-point).
LED_VIIRS_SENSITIVITY_RATIO = 0.55

# Efficiency improvement factor: lumens per watt, LED vs sodium.
# Modern LED ~130 lm/W vs sodium ~100 lm/W → efficiency ratio ~1.30.
LED_EFFICIENCY_RATIO = 1.30

# Net apparent dimming when sodium → LED at same power budget:
#   VIIRS_signal_ratio = LED_sensitivity / LED_efficiency = 0.55 / 1.30 ≈ 0.42
# i.e., same wattage, but VIIRS sees ~42% of former signal.
LED_NET_VIIRS_RATIO = LED_VIIRS_SENSITIVITY_RATIO / LED_EFFICIENCY_RATIO  # ≈ 0.42


# ---------------------------------------------------------------------------
# Known Indian LED penetration rates by state (fraction of street lights that
# are LED as of each year). Source: SLNP Annual Progress Reports (MoP).
# Keys are state names lowercased.
# ---------------------------------------------------------------------------
INDIA_LED_PENETRATION: dict[str, dict[int, float]] = {
    "jammu and kashmir": {
        2015: 0.02, 2016: 0.08, 2017: 0.20, 2018: 0.45,
        2019: 0.65, 2020: 0.78, 2021: 0.85, 2022: 0.90,
        2023: 0.93, 2024: 0.95, 2025: 0.96,
    },
    "uttar pradesh": {
        2015: 0.01, 2016: 0.05, 2017: 0.15, 2018: 0.35,
        2019: 0.55, 2020: 0.70, 2021: 0.80, 2022: 0.87,
        2023: 0.91, 2024: 0.94, 2025: 0.95,
    },
    "maharashtra": {
        2015: 0.03, 2016: 0.10, 2017: 0.22, 2018: 0.42,
        2019: 0.60, 2020: 0.74, 2021: 0.83, 2022: 0.89,
        2023: 0.93, 2024: 0.95, 2025: 0.96,
    },
    "karnataka": {
        2015: 0.04, 2016: 0.12, 2017: 0.25, 2018: 0.47,
        2019: 0.64, 2020: 0.76, 2021: 0.84, 2022: 0.90,
        2023: 0.93, 2024: 0.95, 2025: 0.96,
    },
    "gujarat": {
        2015: 0.05, 2016: 0.15, 2017: 0.30, 2018: 0.52,
        2019: 0.67, 2020: 0.78, 2021: 0.85, 2022: 0.91,
        2023: 0.94, 2024: 0.96, 2025: 0.97,
    },
    "rajasthan": {
        2015: 0.01, 2016: 0.04, 2017: 0.12, 2018: 0.30,
        2019: 0.50, 2020: 0.66, 2021: 0.77, 2022: 0.85,
        2023: 0.89, 2024: 0.92, 2025: 0.94,
    },
    "ladakh": {
        2015: 0.01, 2016: 0.03, 2017: 0.08, 2018: 0.20,
        2019: 0.38, 2020: 0.55, 2021: 0.68, 2022: 0.78,
        2023: 0.85, 2024: 0.89, 2025: 0.91,
    },
    "_default_india": {
        2015: 0.01, 2016: 0.06, 2017: 0.16, 2018: 0.36,
        2019: 0.55, 2020: 0.68, 2021: 0.78, 2022: 0.85,
        2023: 0.90, 2024: 0.93, 2025: 0.95,
    },
}

# ---------------------------------------------------------------------------
# Known rural electrification events (one-time jumps to correct for).
# These are NOT GDP growth events.
# Format: (region_key, year, month, jump_factor)
#   jump_factor: the fraction of the spike that is electrification artefact.
#   0.7 means 70% of a 12-month-averaged radiance jump is electrification.
# ---------------------------------------------------------------------------
ELECTRIFICATION_EVENTS: list[dict] = [
    {
        "region": "ladakh",
        "year": 2017,
        "description": "220kV Srinagar–Leh transmission line energized",
        "jump_factor": 0.70,
    },
    {
        "region": "jammu and kashmir",
        "year": 2019,
        "description": "Saubhagya scheme — near-100% household electrification",
        "jump_factor": 0.30,
    },
    {
        "region": "uttar pradesh",
        "year": 2018,
        "description": "Saubhagya last-mile electrification completion",
        "jump_factor": 0.20,
    },
]


@dataclass
class LightingTechConfig:
    """Configuration for Lighting Technology Adjustment.

    Args:
        led_viirs_ratio: VIIRS sensitivity ratio LED/sodium (default 0.55).
        led_efficiency_ratio: Efficiency ratio LED/sodium lm/W (default 1.30).
        apply_led_correction: If True, correct for LED spectral shift.
        apply_electrification_correction: If True, dampen electrification jumps.
        apply_efficiency_dampening: If True, correct for efficiency improvement.
        state: Indian state name (lowercase) for LED penetration lookup.
        country_code: ISO 3166-1 alpha-3 — non-India regions get generic curve.
        custom_led_penetration: Override {year: fraction} LED penetration series.
        electrification_events: Override list of electrification event dicts.
    """

    led_viirs_ratio: float = LED_VIIRS_SENSITIVITY_RATIO
    led_efficiency_ratio: float = LED_EFFICIENCY_RATIO
    apply_led_correction: bool = True
    apply_electrification_correction: bool = True
    apply_efficiency_dampening: bool = True
    state: Optional[str] = None
    country_code: str = "IND"
    custom_led_penetration: Optional[dict[int, float]] = None
    electrification_events: Optional[list[dict]] = None

    @property
    def net_viirs_ratio(self) -> float:
        """Net VIIRS signal ratio for LED vs sodium at equal power budget."""
        return self.led_viirs_ratio / self.led_efficiency_ratio


def get_led_penetration(
    state: Optional[str],
    years: list[int],
    country_code: str = "IND",
    custom: Optional[dict[int, float]] = None,
) -> dict[int, float]:
    """Return LED street-light penetration rate for each year.

    For India, uses SLNP state-level data. For other countries, returns a
    generic S-curve (global LED penetration trend).

    Args:
        state: State name (lowercase). None → use country default.
        years: Target years.
        country_code: ISO 3166-1 alpha-3.
        custom: Override penetration rates.

    Returns:
        Dict {year: penetration_fraction (0–1)}.
    """
    if custom:
        return interpolate_population(custom, years)

    if country_code == "IND":
        key = (state or "").lower()
        known = INDIA_LED_PENETRATION.get(key, INDIA_LED_PENETRATION["_default_india"])
        return interpolate_population(known, years)

    # Generic global LED S-curve (IEA data)
    global_known = {
        2014: 0.05, 2015: 0.10, 2016: 0.18, 2017: 0.28, 2018: 0.40,
        2019: 0.52, 2020: 0.63, 2021: 0.72, 2022: 0.80, 2023: 0.86,
        2024: 0.90, 2025: 0.93,
    }
    return interpolate_population(global_known, years)


def compute_led_correction_factors(
    years: list[int],
    led_penetration: dict[int, float],
    net_viirs_ratio: float = LED_NET_VIIRS_RATIO,
) -> dict[int, float]:
    """Compute per-year upward correction factor for LED spectral shift.

    When p fraction of lights are LED, the aggregate VIIRS signal is:
        signal = (1 - p) * sodium_signal + p * led_signal
                = (1 - p) * 1 + p * net_viirs_ratio   (sodium baseline = 1)
                = 1 - p * (1 - net_viirs_ratio)

    True luminous output is proportional to 1.0, so correction factor = 1/signal.

    Args:
        years: Target years.
        led_penetration: Dict {year: fraction}.
        net_viirs_ratio: Net VIIRS signal LED/sodium (default ≈ 0.42).

    Returns:
        Dict {year: correction_factor} — multiply observed radiance by this.
    """
    factors = {}
    for yr in years:
        p = led_penetration.get(yr, 0.0)
        p = float(np.clip(p, 0.0, 1.0))
        apparent_signal = 1.0 - p * (1.0 - net_viirs_ratio)
        factors[yr] = 1.0 / apparent_signal if apparent_signal > 0 else 1.0
    return factors


def apply_lighting_tech_adjustment(
    df: pd.DataFrame,
    config: LightingTechConfig,
    radiance_col: str = "radiance_corrected",
    output_col: str = "radiance_lta",
) -> pd.DataFrame:
    """Apply full Lighting Technology Adjustment to a radiance time series.

    Applies in order:
    1. LED spectral correction (upward).
    2. Electrification event dampening (downward, one-time jump only).
    3. Energy-efficiency dampening correction (upward, gradual).

    Args:
        df: Monthly radiance DataFrame with 'year' and radiance_col columns.
        config: LightingTechConfig specifying which corrections to apply.
        radiance_col: Input radiance column (should be cloud-corrected).
        output_col: Output column name for LTA-adjusted radiance.

    Returns:
        DataFrame with output_col added.
    """
    df = df.copy()
    years = sorted(df["year"].unique().tolist())
    rad = df[radiance_col].copy()

    # --- 1. LED spectral correction ---
    if config.apply_led_correction:
        led_pen = get_led_penetration(
            config.state, years,
            country_code=config.country_code,
            custom=config.custom_led_penetration,
        )
        led_factors = compute_led_correction_factors(
            years, led_pen, net_viirs_ratio=config.net_viirs_ratio
        )
        df["_led_factor"] = df["year"].map(led_factors).fillna(1.0)
        rad = rad * df["_led_factor"]
        df.drop(columns=["_led_factor"], inplace=True)

    # --- 2. Electrification event dampening ---
    if config.apply_electrification_correction:
        events = config.electrification_events or _get_relevant_events(config.state, config.country_code)
        for evt in events:
            jump_yr = evt["year"]
            jump_factor = evt.get("jump_factor", 0.0)
            # Dampen the jump year and the year after proportionally
            for offset, weight in [(0, 0.7), (1, 0.3)]:
                mask = df["year"] == (jump_yr + offset)
                if mask.any():
                    # Reduce the jump: multiply by (1 - weight * jump_factor)
                    dampen = 1.0 - weight * jump_factor
                    rad = rad.where(~mask, rad * dampen)

    # --- 3. Energy-efficiency dampening correction ---
    if config.apply_efficiency_dampening:
        # Annual efficiency improvement: ~1.5% per year post-2015
        base_year = min(years)
        for yr in years:
            years_elapsed = max(0, yr - max(base_year, 2015))
            efficiency_gain = (1.015 ** years_elapsed)  # compound
            mask = df["year"] == yr
            rad = rad.where(~mask, rad * efficiency_gain)

    df[output_col] = rad
    return df


def _get_relevant_events(
    state: Optional[str],
    country_code: str,
) -> list[dict]:
    """Filter global electrification events to those relevant for this region."""
    if country_code != "IND":
        return []
    if state is None:
        return []
    state_lower = state.lower()
    return [e for e in ELECTRIFICATION_EVENTS if state_lower in e["region"]]


def lta_correction_summary(
    df: pd.DataFrame,
    radiance_col: str = "radiance_corrected",
    lta_col: str = "radiance_lta",
) -> pd.DataFrame:
    """Per-year summary of the LTA adjustment magnitude.

    Args:
        df: DataFrame after apply_lighting_tech_adjustment().
        radiance_col: Pre-LTA column.
        lta_col: Post-LTA column.

    Returns:
        DataFrame with columns: year, mean_raw, mean_lta, uplift_pct.
    """
    annual = (
        df.groupby("year")[[radiance_col, lta_col]]
        .mean()
        .reset_index()
    )
    annual["uplift_pct"] = (
        (annual[lta_col] - annual[radiance_col]) / annual[radiance_col] * 100
    )
    annual.columns = ["year", "mean_raw", "mean_lta", "uplift_pct"]
    return annual
