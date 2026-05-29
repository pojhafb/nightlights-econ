"""Fast VIIRS extractor using server-side GEE map() — 1 API call per district.

Compared to the original engine.py approach (148 serial calls per district),
this uses ee.ImageCollection.map() to push all reductions to the server and
fetch the entire time series in a single getInfo() call.

All results are transparently cached in SQLite. A cached district costs 0 GEE
calls on repeat runs.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from .cache import (
    geometry_key,
    geometry_key_from_coords,
    geometry_key_from_geojson,
    get_cached,
    save_to_cache,
)
from .utils import RADIANCE_CAP, VIIRS_COLLECTION

DEFAULT_SCALE = 500


def extract_viirs_cached(
    geometry,                    # ee.Geometry
    geo_key: str,                # cache key for this geometry
    start_year: int,
    end_year: int,
    scale: int = DEFAULT_SCALE,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """Fetch monthly VIIRS data, using SQLite cache to avoid repeat GEE calls.

    On first call: hits GEE (1 API call via server-side map), stores result.
    On repeat calls: returns cached data instantly with 0 GEE calls.

    Args:
        geometry: ee.Geometry for the region of interest.
        geo_key: Stable string key for this geometry (use cache.geometry_key()).
        start_year: First year (inclusive).
        end_year: Last year (inclusive).
        scale: GEE reduce scale in metres (default 500).
        force_refresh: If True, bypass cache and re-fetch from GEE.

    Returns:
        DataFrame with columns: date, year, month, radiance_raw, cf_obs.
    """
    if not force_refresh:
        cached = get_cached(geo_key, start_year, end_year, scale)
        if cached is not None:
            return cached

    df = _fetch_from_gee(geometry, start_year, end_year, scale)
    save_to_cache(geo_key, start_year, end_year, scale, df)
    return df


def _fetch_from_gee(
    geometry,
    start_year: int,
    end_year: int,
    scale: int,
) -> pd.DataFrame:
    """Single-call GEE extraction using server-side ImageCollection.map()."""
    try:
        import ee
    except ImportError:
        raise ImportError("earthengine-api required. Run: pip install earthengine-api")

    col = (
        ee.ImageCollection(VIIRS_COLLECTION)
        .filterDate(f"{start_year}-01-01", f"{end_year + 1}-01-01")
        .filterBounds(geometry)
    )

    def _reduce_image(img):
        reduced = (
            img.select("avg_rad")
               .min(ee.Image.constant(RADIANCE_CAP))
               .rename("avg_rad")
               .addBands(img.select("cf_cvg").rename("cf_cvg"))
               .reduceRegion(
                   reducer=ee.Reducer.mean(),
                   geometry=geometry,
                   scale=scale,
                   maxPixels=1e9,
               )
        )
        return ee.Feature(None, {
            "time":    img.get("system:time_start"),
            "avg_rad": reduced.get("avg_rad"),
            "cf_cvg":  reduced.get("cf_cvg"),
        })

    # Single getInfo() call — all months fetched in one round trip
    fc_info = col.map(_reduce_image).getInfo()

    records = []
    for feat in fc_info.get("features", []):
        props = feat.get("properties", {})
        ts = props.get("time")
        if ts is None:
            continue
        date = pd.Timestamp(ts, unit="ms")
        records.append({
            "date":         date,
            "year":         date.year,
            "month":        date.month,
            "radiance_raw": float(props["avg_rad"]) if props.get("avg_rad") is not None else float("nan"),
            "cf_obs":       float(props["cf_cvg"])  if props.get("cf_cvg")  is not None else float("nan"),
        })

    if not records:
        raise RuntimeError(
            f"No VIIRS data returned for {start_year}–{end_year}. "
            "Check that the geometry intersects the VIIRS coverage area."
        )

    df = pd.DataFrame(records).sort_values("date").reset_index(drop=True)
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Convenience wrappers that handle geometry key generation
# ─────────────────────────────────────────────────────────────────────────────

def extract_for_district(
    admin2: str,
    admin1: str,
    country: str,
    start_year: int,
    end_year: int,
    scale: int = DEFAULT_SCALE,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """Extract VIIRS for an administrative district, with caching.

    Resolves the GAUL boundary automatically.

    Args:
        admin2: District name (GAUL ADM2_NAME).
        admin1: State name (GAUL ADM1_NAME).
        country: Country name (GAUL ADM0_NAME).
        start_year: First year.
        end_year: Last year.
        scale: GEE reduce scale in metres.
        force_refresh: Bypass cache.

    Returns:
        DataFrame with date, year, month, radiance_raw, cf_obs.
    """
    import ee
    geo_key = geometry_key(admin2, admin1, country)
    cached = None if force_refresh else get_cached(geo_key, start_year, end_year, scale)
    if cached is not None:
        return cached

    gaul = ee.FeatureCollection("FAO/GAUL/2015/level2")
    geom = (gaul
            .filter(ee.Filter.eq("ADM2_NAME", admin2))
            .filter(ee.Filter.eq("ADM1_NAME", admin1))
            .filter(ee.Filter.eq("ADM0_NAME", country))
            .first()
            .geometry())

    return extract_viirs_cached(geom, geo_key, start_year, end_year, scale, force_refresh)


def extract_for_point(
    lat: float,
    lon: float,
    radius_km: float,
    start_year: int,
    end_year: int,
    scale: int = DEFAULT_SCALE,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """Extract VIIRS for a point+radius geometry, with caching."""
    import ee
    geo_key = geometry_key_from_coords(lat, lon, radius_km)
    cached = None if force_refresh else get_cached(geo_key, start_year, end_year, scale)
    if cached is not None:
        return cached

    geom = ee.Geometry.Point([lon, lat]).buffer(radius_km * 1000)
    return extract_viirs_cached(geom, geo_key, start_year, end_year, scale, force_refresh)
