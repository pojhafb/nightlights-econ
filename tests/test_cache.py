"""Tests for the SQLite VIIRS cache."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

import nightlights_econ.cache as cache_module
from nightlights_econ.cache import (
    geometry_key,
    geometry_key_from_coords,
    get_cached,
    save_to_cache,
    cache_info,
    invalidate,
    invalidate_all,
)


@pytest.fixture(autouse=True)
def tmp_cache(tmp_path):
    """Redirect cache DB to a temp directory for every test."""
    with patch.object(cache_module, "DB_PATH", tmp_path / "test_cache.db"):
        with patch.object(cache_module, "CACHE_DIR", tmp_path):
            yield tmp_path


@pytest.fixture
def sample_df():
    dates = pd.date_range("2020-01-01", periods=12, freq="MS")
    return pd.DataFrame({
        "date": dates,
        "year": dates.year,
        "month": dates.month,
        "radiance_raw": np.random.uniform(2, 8, 12),
        "cf_obs": np.random.uniform(4, 14, 12),
    })


def test_geometry_key_stable():
    k1 = geometry_key("Pune", "Maharashtra", "India")
    k2 = geometry_key("Pune", "Maharashtra", "India")
    assert k1 == k2


def test_geometry_key_case_insensitive():
    k1 = geometry_key("pune", "maharashtra", "india")
    k2 = geometry_key("Pune", "Maharashtra", "India")
    assert k1 == k2


def test_geometry_key_differs_by_district():
    k1 = geometry_key("Pune", "Maharashtra", "India")
    k2 = geometry_key("Mumbai", "Maharashtra", "India")
    assert k1 != k2


def test_cache_miss_returns_none():
    result = get_cached("nonexistent_key", 2014, 2026, 500)
    assert result is None


def test_save_and_retrieve(sample_df):
    key = geometry_key("Pune", "Maharashtra")
    save_to_cache(key, 2020, 2020, 500, sample_df)
    result = get_cached(key, 2020, 2020, 500)
    assert result is not None
    assert len(result) == len(sample_df)
    assert list(result.columns) == ["date", "year", "month", "radiance_raw", "cf_obs"]


def test_cache_respects_year_range(sample_df):
    key = geometry_key("Chennai", "Tamil Nadu")
    # Save 2020 data
    save_to_cache(key, 2020, 2020, 500, sample_df)
    # Request 2019–2020 — should miss (cache only has 2020)
    result = get_cached(key, 2019, 2020, 500)
    assert result is None
    # Request exactly 2020 — should hit
    result = get_cached(key, 2020, 2020, 500)
    assert result is not None


def test_cache_respects_scale(sample_df):
    key = geometry_key("Lucknow", "Uttar Pradesh")
    save_to_cache(key, 2020, 2020, 500, sample_df)
    # Different scale → cache miss
    assert get_cached(key, 2020, 2020, 1000) is None
    # Same scale → cache hit
    assert get_cached(key, 2020, 2020, 500) is not None


def test_overwrite_on_resave(sample_df):
    key = geometry_key("Varanasi", "Uttar Pradesh")
    save_to_cache(key, 2020, 2020, 500, sample_df)

    new_df = sample_df.copy()
    new_df["radiance_raw"] = 99.0
    save_to_cache(key, 2020, 2020, 500, new_df)

    result = get_cached(key, 2020, 2020, 500)
    assert result["radiance_raw"].iloc[0] == pytest.approx(99.0)


def test_nan_values_survive_roundtrip():
    dates = pd.date_range("2020-01-01", periods=3, freq="MS")
    df = pd.DataFrame({
        "date": dates,
        "year": dates.year,
        "month": dates.month,
        "radiance_raw": [1.0, float("nan"), 3.0],
        "cf_obs": [10.0, 10.0, float("nan")],
    })
    key = geometry_key("TestCity", "TestState")
    save_to_cache(key, 2020, 2020, 500, df)
    result = get_cached(key, 2020, 2020, 500)
    assert pd.isna(result["radiance_raw"].iloc[1])
    assert pd.isna(result["cf_obs"].iloc[2])


def test_cache_info_returns_dataframe(sample_df):
    key = geometry_key("Bengaluru", "Karnataka")
    save_to_cache(key, 2020, 2020, 500, sample_df)
    info = cache_info()
    assert len(info) >= 1
    assert "geometry_key" in info.columns
    assert "n_rows" in info.columns


def test_invalidate_removes_entry(sample_df):
    key = geometry_key("Hyderabad", "Andhra Pradesh")
    save_to_cache(key, 2020, 2020, 500, sample_df)
    assert get_cached(key, 2020, 2020, 500) is not None
    removed = invalidate(key, 2020, 2020, 500)
    assert removed is True
    assert get_cached(key, 2020, 2020, 500) is None


def test_invalidate_all(sample_df):
    for name in ["CityA", "CityB", "CityC"]:
        save_to_cache(geometry_key(name, "State"), 2020, 2020, 500, sample_df)
    count = invalidate_all()
    assert count == 3
    assert len(cache_info()) == 0


def test_multiple_districts_independent(sample_df):
    k1 = geometry_key("CityX", "State1")
    k2 = geometry_key("CityY", "State1")
    df2 = sample_df.copy()
    df2["radiance_raw"] = 50.0

    save_to_cache(k1, 2020, 2020, 500, sample_df)
    save_to_cache(k2, 2020, 2020, 500, df2)

    r1 = get_cached(k1, 2020, 2020, 500)
    r2 = get_cached(k2, 2020, 2020, 500)
    assert not (r1["radiance_raw"].values == r2["radiance_raw"].values).all()
