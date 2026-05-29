"""DMSP-OLS extraction and cross-calibration to VIIRS units.

Extends nighttime lights analysis back to 2004 using the
NOAA/DMSP-OLS/NIGHTTIME_LIGHTS collection, cross-calibrated to VIIRS
radiance units at the 2013 overlap year.

Key limitations vs VIIRS:
- Annual composites only (no monthly granularity)
- ~2.7 km resolution vs ~500 m for VIIRS
- stable_lights band saturates at 63 DN over bright urban cores
- No cloud-free observation count → monsoon correction not applicable
- Calibration uncertainty ~15-30%

Reference for cross-calibration approach:
  Liu et al. (2012) "Extracting the dynamics of urban expansion..."
  Elvidge et al. (2014) "National trends in satellite observed lighting..."
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from .cache import geometry_key as _geo_key, get_cached, save_to_cache

DMSP_COLLECTION = "NOAA/DMSP-OLS/NIGHTTIME_LIGHTS"
DMSP_BAND = "stable_lights"        # removes gas flares and fires
DMSP_MAX_DN = 63.0                 # 6-bit saturation ceiling
DMSP_SCALE = 2700                  # native ~2.7 km resolution (used as cache key)

# Satellite images available per year (index names in GEE)
# When multiple satellites overlap, we average them.
DMSP_IMAGES_BY_YEAR: dict[int, list[str]] = {
    2004: ["F152004", "F162004"],
    2005: ["F152005", "F162005"],
    2006: ["F152006", "F162006"],
    2007: ["F152007", "F162007"],
    2008: ["F152008", "F162008"],
    2009: ["F162009"],
    2010: ["F182010"],
    2011: ["F182011"],
    2012: ["F182012"],
    2013: ["F182013"],
}

VIIRS_CALIB_COLLECTION = "NOAA/VIIRS/DNB/MONTHLY_V1/VCMCFG"


def _cache_key_dmsp(geo_key: str) -> str:
    """Separate cache namespace for DMSP data."""
    return f"dmsp:{geo_key}"


def extract_dmsp_annual(
    geometry,
    geo_key: str,
    start_year: int = 2004,
    end_year: int = 2013,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """Extract DMSP annual mean stable_lights for a geometry.

    Results are cached in SQLite (scale=DMSP_SCALE as distinguishing key).

    Args:
        geometry: ee.Geometry.
        geo_key: Cache key for this geometry.
        start_year: First year (min 2004).
        end_year: Last year (max 2013).
        force_refresh: Bypass cache.

    Returns:
        DataFrame with columns: year, radiance_raw (mean DN, 0-63 scale).
    """
    key = _cache_key_dmsp(geo_key)
    if not force_refresh:
        cached = get_cached(key, start_year, end_year, DMSP_SCALE)
        if cached is not None:
            return cached

    df = _fetch_dmsp_from_gee(geometry, start_year, end_year)
    save_to_cache(key, start_year, end_year, DMSP_SCALE, df)
    return df


def _fetch_dmsp_from_gee(
    geometry,
    start_year: int,
    end_year: int,
) -> pd.DataFrame:
    """Fetch DMSP annual mean stable_lights from GEE, averaging multi-satellite years."""
    try:
        import ee
    except ImportError:
        raise ImportError("earthengine-api required.")

    col = ee.ImageCollection(DMSP_COLLECTION)
    records = []

    for yr in range(start_year, end_year + 1):
        img_ids = DMSP_IMAGES_BY_YEAR.get(yr, [])
        if not img_ids:
            continue

        # Average all satellites for this year
        images = [col.filter(ee.Filter.eq("system:index", img_id)).first()
                  for img_id in img_ids]

        if len(images) == 1:
            combined = images[0].select(DMSP_BAND)
        else:
            combined = ee.ImageCollection(images).select(DMSP_BAND).mean()

        result = combined.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=geometry,
            scale=DMSP_SCALE,
            maxPixels=1e9,
        ).getInfo()

        val = result.get(DMSP_BAND)
        records.append({
            "date":         pd.Timestamp(f"{yr}-07-01"),   # mid-year for annual
            "year":         yr,
            "month":        7,
            "radiance_raw": float(val) if val is not None else float("nan"),
            "cf_obs":       float("nan"),  # not available for DMSP
        })

    if not records:
        raise RuntimeError(f"No DMSP data returned for {start_year}–{end_year}.")

    return pd.DataFrame(records).sort_values("year").reset_index(drop=True)


def compute_viirs_annual_mean(
    geometry,
    year: int,
    scale: int = 500,
) -> float:
    """Compute VIIRS VCMCFG annual mean radiance for a single year.

    Used for cross-calibration at the 2013 overlap.

    Args:
        geometry: ee.Geometry.
        year: Calendar year.
        scale: GEE reduce scale.

    Returns:
        Mean radiance in nW/cm²/sr.
    """
    try:
        import ee
    except ImportError:
        raise ImportError("earthengine-api required.")

    col = (
        ee.ImageCollection(VIIRS_CALIB_COLLECTION)
        .filterDate(f"{year}-01-01", f"{year + 1}-01-01")
        .filterBounds(geometry)
    )

    mean_img = col.select("avg_rad").mean()
    result = mean_img.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=geometry,
        scale=scale,
        maxPixels=1e9,
    ).getInfo()

    val = result.get("avg_rad")
    return float(val) if val is not None else float("nan")


def cross_calibrate_dmsp_to_viirs(
    dmsp_df: pd.DataFrame,
    viirs_mean_2013: float,
    dmsp_mean_2013: Optional[float] = None,
) -> pd.DataFrame:
    """Scale DMSP DN values to VIIRS-equivalent nW/cm²/sr units.

    Uses a per-district linear calibration anchored at the 2013 overlap year:
        viirs_equiv(year) = dmsp_dn(year) * (viirs_2013 / dmsp_2013)

    Args:
        dmsp_df: DataFrame from extract_dmsp_annual() with 'radiance_raw' in DN.
        viirs_mean_2013: VIIRS annual mean for 2013 (nW/cm²/sr).
        dmsp_mean_2013: DMSP DN for 2013 (auto-extracted from dmsp_df if None).

    Returns:
        DataFrame with 'radiance_raw' replaced by calibrated VIIRS-equivalent values,
        and 'radiance_corrected' = same (no cloud correction for DMSP),
        and 'calibrated' = True flag column.
    """
    df = dmsp_df.copy()

    if dmsp_mean_2013 is None:
        row_2013 = df[df["year"] == 2013]
        dmsp_mean_2013 = float(row_2013["radiance_raw"].iloc[0]) if not row_2013.empty else float("nan")

    if np.isnan(dmsp_mean_2013) or dmsp_mean_2013 <= 0:
        raise ValueError("DMSP 2013 mean is zero or NaN — cannot calibrate.")

    if np.isnan(viirs_mean_2013) or viirs_mean_2013 <= 0:
        raise ValueError("VIIRS 2013 mean is zero or NaN — cannot calibrate.")

    scale_factor = viirs_mean_2013 / dmsp_mean_2013

    df["radiance_raw"] = df["radiance_raw"] * scale_factor
    df["radiance_corrected"] = df["radiance_raw"].copy()  # no cloud correction for DMSP
    df["radiance_lta"] = df["radiance_raw"].copy()        # LTA negligible pre-2015
    df["calibration_factor"] = scale_factor
    df["source"] = "DMSP-OLS (calibrated)"
    return df


def build_unified_series(
    dmsp_calibrated: pd.DataFrame,
    viirs_annual: pd.DataFrame,
) -> pd.DataFrame:
    """Splice DMSP (2004-2013) and VIIRS (2014+) into one annual series.

    At the splice year, uses VIIRS (preferred over DMSP).
    Adds a 'source' column to track provenance.

    Args:
        dmsp_calibrated: Output of cross_calibrate_dmsp_to_viirs().
        viirs_annual: Annual-averaged VIIRS DataFrame (from monthly series).
            Must have columns: year, radiance_corrected, radiance_lta.

    Returns:
        Unified annual DataFrame.
    """
    viirs_annual = viirs_annual.copy()
    viirs_annual["source"] = "VIIRS"

    dmsp_only = dmsp_calibrated[dmsp_calibrated["year"] < viirs_annual["year"].min()].copy()
    combined = pd.concat([dmsp_only, viirs_annual], ignore_index=True)
    return combined.sort_values("year").reset_index(drop=True)
