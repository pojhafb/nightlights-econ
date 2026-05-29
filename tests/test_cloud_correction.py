"""Tests for the xKDR cloud-bias correction algorithm."""

import numpy as np
import pandas as pd
import pytest

from nightlights_econ.cloud_correction import correct_cloud_bias, correction_stats
from nightlights_econ.utils import CF_OBS_THRESHOLD


def test_monsoon_months_corrected_upward(mock_radiance_data):
    """Months with low cloud-free obs should be corrected upward or left unchanged."""
    df = correct_cloud_bias(mock_radiance_data)
    cloudy = df[df["cf_obs"] < CF_OBS_THRESHOLD]
    assert not cloudy.empty, "Expected some cloudy months in mock data"
    assert (cloudy["radiance_corrected"] >= cloudy["radiance_raw"]).all(), (
        "Correction must never decrease radiance"
    )


def test_clear_months_unchanged(mock_radiance_data):
    """Months above the cf_obs threshold should be passed through unchanged."""
    df = correct_cloud_bias(mock_radiance_data)
    clear = df[df["cf_obs"] >= CF_OBS_THRESHOLD]
    assert not clear.empty
    np.testing.assert_array_almost_equal(
        clear["radiance_corrected"].values,
        clear["radiance_raw"].values,
        decimal=6,
    )


def test_correction_only_upward(mock_radiance_data):
    """All corrected values must be >= raw values (bias is always downward)."""
    df = correct_cloud_bias(mock_radiance_data)
    diff = df["radiance_corrected"] - df["radiance_raw"]
    assert (diff.fillna(0) >= -1e-9).all(), "Correction must be monotonically non-negative"


def test_edge_all_clear():
    """All months clear → corrected should equal raw."""
    dates = pd.date_range("2020-01-01", periods=12, freq="MS")
    df = pd.DataFrame({
        "date": dates,
        "year": dates.year,
        "month": dates.month,
        "radiance_raw": np.full(12, 5.0),
        "cf_obs": np.full(12, 12.0),
    })
    result = correct_cloud_bias(df)
    np.testing.assert_array_almost_equal(
        result["radiance_corrected"].values,
        result["radiance_raw"].values,
    )


def test_edge_all_cloudy():
    """All months below threshold → fallback correction should not crash."""
    dates = pd.date_range("2020-01-01", periods=12, freq="MS")
    np.random.seed(0)
    df = pd.DataFrame({
        "date": dates,
        "year": dates.year,
        "month": dates.month,
        "radiance_raw": np.random.uniform(2, 4, 12),
        "cf_obs": np.full(12, 2.0),
    })
    result = correct_cloud_bias(df)
    assert "radiance_corrected" in result.columns
    assert not result["radiance_corrected"].isna().all()


def test_custom_threshold(mock_radiance_data):
    """Custom cf_threshold should be respected."""
    df_strict = correct_cloud_bias(mock_radiance_data, cf_threshold=12)
    cloudy_strict = df_strict[df_strict["cf_obs"] < 12]
    assert (cloudy_strict["radiance_corrected"] >= cloudy_strict["radiance_raw"]).all()


def test_correction_stats(mock_radiance_data):
    """correction_stats should return sensible summary dict."""
    df = correct_cloud_bias(mock_radiance_data)
    stats = correction_stats(df)
    assert "n_corrected" in stats
    assert "mean_uplift_pct" in stats
    assert stats["months_below_threshold"] == (df["cf_obs"] < CF_OBS_THRESHOLD).sum()
    assert stats["mean_uplift_pct"] >= 0


def test_nan_propagation():
    """NaN radiance values should remain NaN after correction."""
    dates = pd.date_range("2020-01-01", periods=6, freq="MS")
    df = pd.DataFrame({
        "date": dates,
        "year": dates.year,
        "month": dates.month,
        "radiance_raw": [5.0, np.nan, 5.0, 3.0, 2.0, 4.0],
        "cf_obs": [10.0, 10.0, 10.0, 2.0, 2.0, 10.0],
    })
    result = correct_cloud_bias(df)
    assert np.isnan(result["radiance_corrected"].iloc[1])
