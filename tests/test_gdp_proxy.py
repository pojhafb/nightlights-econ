"""Tests for the Henderson GDP proxy model."""

import numpy as np
import pandas as pd
import pytest

from nightlights_econ.gdp_proxy import (
    compute_gdp_proxy,
    compute_gdp_per_capita,
    compute_ppp_adjusted,
    compute_all_metrics,
)
from nightlights_econ.cloud_correction import correct_cloud_bias
from nightlights_econ.utils import HENDERSON_ELASTICITY


def _make_df(mock_radiance_data):
    """Return corrected radiance DataFrame."""
    return correct_cloud_bias(mock_radiance_data)


def test_base_year_is_100(mock_radiance_data):
    """The mean GDP proxy index in base year should equal 100."""
    df = _make_df(mock_radiance_data)
    df = compute_gdp_proxy(df, base_year=2014)
    base_mean = df[df["year"] == 2014]["gdp_proxy"].mean()
    assert abs(base_mean - 100.0) < 1.0, f"Base year mean should be ~100, got {base_mean}"


def test_elasticity_applied(mock_radiance_data):
    """Doubling radiance with elasticity 0.88 should give 2^0.88 ~ 1.836× growth."""
    df = _make_df(mock_radiance_data)
    # Construct synthetic data: base=5, double=10
    df2 = df.copy()
    df2["radiance_corrected"] = 5.0
    df2.loc[df2["year"] == 2020, "radiance_corrected"] = 10.0
    result = compute_gdp_proxy(df2, base_year=2014, elasticity=HENDERSON_ELASTICITY)
    mean_2020 = result[result["year"] == 2020]["gdp_proxy"].mean()
    expected = 100.0 * (2.0 ** HENDERSON_ELASTICITY)
    assert abs(mean_2020 - expected) < 2.0, f"Expected ~{expected:.1f}, got {mean_2020:.1f}"


def test_custom_elasticity(mock_radiance_data):
    """A custom elasticity of 1.0 should give linear radiance ratio."""
    df = _make_df(mock_radiance_data)
    df["radiance_corrected"] = 5.0
    df.loc[df["year"] == 2020, "radiance_corrected"] = 10.0
    result = compute_gdp_proxy(df, base_year=2014, elasticity=1.0)
    mean_2020 = result[result["year"] == 2020]["gdp_proxy"].mean()
    assert abs(mean_2020 - 200.0) < 1.0


def test_per_capita_divides_properly(mock_radiance_data, mock_population):
    """Per-capita should track GDP proxy but adjusted for population growth."""
    df = _make_df(mock_radiance_data)
    df = compute_gdp_proxy(df, base_year=2014)
    df = compute_gdp_per_capita(df, mock_population, base_year=2014)

    assert "gdp_per_capita" in df.columns
    base_mean = df[df["year"] == 2014]["gdp_per_capita"].mean()
    assert abs(base_mean - 100.0) < 1.0


def test_ppp_adjustment_relative(mock_radiance_data, mock_population, mock_ppp_factors):
    """PPP-adjusted base year should also be ~100 (relative normalization)."""
    df = _make_df(mock_radiance_data)
    df = compute_gdp_proxy(df, base_year=2014)
    df = compute_gdp_per_capita(df, mock_population, base_year=2014)
    df = compute_ppp_adjusted(df, mock_ppp_factors, base_year=2014)

    base_mean = df[df["year"] == 2014]["gdp_ppp_per_capita"].mean()
    assert abs(base_mean - 100.0) < 1.0


def test_ppp_diverges_from_nominal_over_time(mock_radiance_data, mock_population, mock_ppp_factors):
    """PPP-adjusted and nominal should diverge as PPP factor changes."""
    df = _make_df(mock_radiance_data)
    df = compute_gdp_proxy(df, base_year=2014)
    df = compute_gdp_per_capita(df, mock_population, base_year=2014)
    df = compute_ppp_adjusted(df, mock_ppp_factors, base_year=2014)

    late = df[df["year"] == 2024]
    diff = abs(late["gdp_per_capita"].mean() - late["gdp_ppp_per_capita"].mean())
    assert diff > 0.5, "PPP and nominal should differ in later years"


def test_compute_all_metrics_chain(mock_radiance_data, mock_population, mock_ppp_factors):
    """compute_all_metrics should add all three output columns."""
    df = correct_cloud_bias(mock_radiance_data)
    result = compute_all_metrics(
        df, base_year=2014,
        population_by_year=mock_population,
        ppp_factors=mock_ppp_factors,
    )
    for col in ["gdp_proxy", "gdp_per_capita", "gdp_ppp_per_capita"]:
        assert col in result.columns, f"Missing column: {col}"
        assert not result[col].isna().all(), f"Column {col} is all NaN"


def test_zero_radiance_gives_nan(mock_radiance_data, mock_population, mock_ppp_factors):
    """Zero radiance should produce NaN in GDP proxy (log/power undefined)."""
    df = correct_cloud_bias(mock_radiance_data)
    df["radiance_corrected"] = df["radiance_corrected"].where(df["year"] != 2020, 0.0)
    result = compute_gdp_proxy(df, base_year=2014)
    zero_rows = result[result["year"] == 2020]
    assert zero_rows["gdp_proxy"].isna().all() or (zero_rows["gdp_proxy"] == 0).all()
