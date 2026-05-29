"""Shared utility helpers."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd


MONSOON_MONTHS = {6, 7, 8, 9}
VIIRS_COLLECTION = "NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG"
RADIANCE_BAND = "avg_rad"
CF_BAND = "cf_cvg"
RADIANCE_CAP = 100.0  # nW/cm²/sr — excludes gas flares/fires
CF_OBS_THRESHOLD = 8   # below this → apply cloud correction
HENDERSON_ELASTICITY = 0.88

CACHE_DIR = Path.home() / ".cache" / "nightlights_econ"


def ensure_cache_dir() -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR


def load_json_cache(filename: str) -> dict:
    path = CACHE_DIR / filename
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


def save_json_cache(filename: str, data: dict) -> None:
    ensure_cache_dir()
    path = CACHE_DIR / filename
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def date_range_monthly(start_year: int, end_year: int) -> pd.DatetimeIndex:
    """Return monthly date range from Jan start_year to Dec end_year."""
    return pd.date_range(
        f"{start_year}-01-01",
        f"{end_year}-12-01",
        freq="MS",
    )


def is_monsoon(month: int) -> bool:
    return month in MONSOON_MONTHS


def index_to_base(series: pd.Series, base_year: int, year_series: pd.Series) -> pd.Series:
    """Normalize a series so that the mean value in base_year = 100."""
    base_mask = year_series == base_year
    base_val = series[base_mask].mean()
    if base_val == 0 or np.isnan(base_val):
        return series * np.nan
    return (series / base_val) * 100.0


def yoy_growth(series: pd.Series) -> pd.Series:
    """Year-over-year percentage growth."""
    return series.pct_change(periods=12) * 100.0


def compound_growth_rate(values: dict[int, float], from_year: int, to_year: int) -> float:
    """CAGR between two years given a dict of {year: value}."""
    if from_year not in values or to_year not in values:
        raise KeyError(f"Years {from_year} or {to_year} not in values dict.")
    n = to_year - from_year
    if n == 0:
        return 0.0
    return (values[to_year] / values[from_year]) ** (1.0 / n) - 1.0


def interpolate_population(
    known: dict[int, float],
    target_years: list[int],
) -> dict[int, float]:
    """Linearly interpolate/extrapolate population for target years.

    Args:
        known: Dict of {year: population} at known epochs.
        target_years: Years for which to estimate population.

    Returns:
        Dict {year: population} for all target years.
    """
    sorted_years = sorted(known.keys())
    sorted_vals = [known[y] for y in sorted_years]

    result = {}
    for yr in target_years:
        if yr in known:
            result[yr] = known[yr]
        elif yr < sorted_years[0]:
            # Extrapolate backward using first two known points
            if len(sorted_years) >= 2:
                cagr = compound_growth_rate(known, sorted_years[0], sorted_years[1])
                result[yr] = known[sorted_years[0]] * (1 + cagr) ** (yr - sorted_years[0])
            else:
                result[yr] = sorted_vals[0]
        elif yr > sorted_years[-1]:
            # Extrapolate forward using last two known points
            if len(sorted_years) >= 2:
                cagr = compound_growth_rate(known, sorted_years[-2], sorted_years[-1])
                result[yr] = known[sorted_years[-1]] * (1 + cagr) ** (yr - sorted_years[-1])
            else:
                result[yr] = sorted_vals[-1]
        else:
            # Linear interpolation
            result[yr] = float(np.interp(yr, sorted_years, sorted_vals))
    return result


def safe_save(fig, save_path: Optional[str], dpi: int = 150) -> None:
    """Save a matplotlib figure if save_path is provided."""
    if save_path is not None:
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_path, dpi=dpi, bbox_inches="tight")
