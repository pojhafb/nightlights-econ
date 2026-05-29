"""Tests for the Lighting Technology Adjustment module."""

import numpy as np
import pandas as pd
import pytest

from nightlights_econ.lighting_tech import (
    LightingTechConfig,
    apply_lighting_tech_adjustment,
    compute_led_correction_factors,
    get_led_penetration,
    lta_correction_summary,
    LED_NET_VIIRS_RATIO,
    INDIA_LED_PENETRATION,
)


@pytest.fixture
def sample_df():
    """Monthly radiance DataFrame covering 2014–2026."""
    dates = pd.date_range("2014-01-01", "2026-12-01", freq="MS")
    np.random.seed(7)
    return pd.DataFrame({
        "date": dates,
        "year": dates.year,
        "month": dates.month,
        "radiance_corrected": np.random.uniform(3.0, 8.0, len(dates)),
    })


def test_led_correction_factors_no_penetration():
    """At 0% LED penetration, correction factor should be 1.0."""
    factors = compute_led_correction_factors([2014], {2014: 0.0})
    assert abs(factors[2014] - 1.0) < 1e-9


def test_led_correction_factors_full_penetration():
    """At 100% LED penetration, factor = 1 / net_viirs_ratio."""
    factors = compute_led_correction_factors([2020], {2020: 1.0}, net_viirs_ratio=LED_NET_VIIRS_RATIO)
    expected = 1.0 / LED_NET_VIIRS_RATIO
    assert abs(factors[2020] - expected) < 1e-6


def test_led_correction_factors_always_gte_1():
    """Correction factors should always be ≥ 1.0 (only upward correction)."""
    pen = {yr: yr * 0.07 - 2014 * 0.07 for yr in range(2014, 2027)}
    factors = compute_led_correction_factors(list(range(2014, 2027)), pen)
    for yr, f in factors.items():
        assert f >= 1.0 - 1e-9, f"Factor for {yr} is {f} < 1.0"


def test_led_penetration_india_state():
    """Should return state-specific rates for known Indian states."""
    pen = get_led_penetration("uttar pradesh", list(range(2014, 2027)), country_code="IND")
    assert pen[2014] <= pen[2022], "LED penetration should increase over time"
    assert pen[2022] > 0.8


def test_led_penetration_unknown_state_uses_default():
    """Unknown state should fall back to _default_india."""
    pen = get_led_penetration("zz unknown state", list(range(2014, 2027)), country_code="IND")
    default = get_led_penetration(None, list(range(2014, 2027)), country_code="IND")
    assert pen == default


def test_led_penetration_non_india_global_curve():
    """Non-India countries should use the global S-curve."""
    pen = get_led_penetration(None, [2015, 2020, 2025], country_code="UKR")
    assert pen[2015] < pen[2020] < pen[2025]
    assert pen[2025] > 0.8


def test_led_penetration_custom_override():
    """Custom penetration dict should be used as-is."""
    custom = {2014: 0.10, 2020: 0.80}
    pen = get_led_penetration(None, [2014, 2017, 2020], custom=custom)
    assert pen[2014] == 0.10
    assert pen[2020] == 0.80
    # 2017 should be interpolated between
    assert 0.10 < pen[2017] < 0.80


def test_apply_lta_led_only_increases_radiance(sample_df):
    """LED-only correction should increase or maintain all radiance values."""
    config = LightingTechConfig(
        apply_led_correction=True,
        apply_electrification_correction=False,
        apply_efficiency_dampening=False,
        state="uttar pradesh",
        country_code="IND",
    )
    result = apply_lighting_tech_adjustment(sample_df, config)
    assert "radiance_lta" in result.columns
    diff = result["radiance_lta"] - result["radiance_corrected"]
    assert (diff >= -1e-9).all(), "LED correction should never decrease radiance"


def test_apply_lta_base_year_unchanged(sample_df):
    """In 2014 (≈0% LED penetration), correction should be negligible."""
    config = LightingTechConfig(
        apply_led_correction=True,
        apply_electrification_correction=False,
        apply_efficiency_dampening=False,
        state="maharashtra",
        country_code="IND",
    )
    result = apply_lighting_tech_adjustment(sample_df, config)
    base = result[result["year"] == 2014]
    diff_pct = abs((base["radiance_lta"] - base["radiance_corrected"]) / base["radiance_corrected"] * 100)
    assert (diff_pct < 2.0).all(), "2014 correction should be < 2% (very low LED penetration)"


def test_apply_lta_later_years_larger_correction(sample_df):
    """Correction in 2022 should exceed correction in 2015 (more LED by then)."""
    config = LightingTechConfig(
        apply_led_correction=True,
        apply_electrification_correction=False,
        apply_efficiency_dampening=False,
        state="maharashtra",
    )
    result = apply_lighting_tech_adjustment(sample_df, config)
    ratio_2015 = (result[result["year"] == 2015]["radiance_lta"] /
                  result[result["year"] == 2015]["radiance_corrected"]).mean()
    ratio_2022 = (result[result["year"] == 2022]["radiance_lta"] /
                  result[result["year"] == 2022]["radiance_corrected"]).mean()
    assert ratio_2022 > ratio_2015


def test_electrification_correction_dampens_leh(sample_df):
    """Ladakh 2017 electrification event should reduce the radiance in that year."""
    # Add an artificial spike in 2017 to simulate the electrification jump
    df = sample_df.copy()
    df.loc[df["year"] == 2017, "radiance_corrected"] *= 2.0

    config = LightingTechConfig(
        apply_led_correction=False,
        apply_electrification_correction=True,
        apply_efficiency_dampening=False,
        state="ladakh",
    )
    result = apply_lighting_tech_adjustment(df, config)
    mean_2017_raw = df[df["year"] == 2017]["radiance_corrected"].mean()
    mean_2017_lta = result[result["year"] == 2017]["radiance_lta"].mean()
    assert mean_2017_lta < mean_2017_raw, "Electrification dampening should reduce 2017 radiance"


def test_efficiency_dampening_increases_later_years(sample_df):
    """Efficiency correction should increase radiance in later years."""
    config = LightingTechConfig(
        apply_led_correction=False,
        apply_electrification_correction=False,
        apply_efficiency_dampening=True,
    )
    result = apply_lighting_tech_adjustment(sample_df, config)
    ratio_2025 = (result[result["year"] == 2025]["radiance_lta"] /
                  result[result["year"] == 2025]["radiance_corrected"]).mean()
    ratio_2015 = (result[result["year"] == 2015]["radiance_lta"] /
                  result[result["year"] == 2015]["radiance_corrected"]).mean()
    assert ratio_2025 > ratio_2015


def test_lta_summary_columns(sample_df):
    """lta_correction_summary should return expected columns."""
    config = LightingTechConfig(state="maharashtra")
    result = apply_lighting_tech_adjustment(sample_df, config)
    summary = lta_correction_summary(result)
    for col in ["year", "mean_raw", "mean_lta", "uplift_pct"]:
        assert col in summary.columns
    assert len(summary) == len(sample_df["year"].unique())


def test_full_pipeline_with_lta(mock_radiance_data, mock_population, mock_ppp_factors):
    """End-to-end: cloud correction → LTA → GDP proxy should all succeed."""
    from nightlights_econ.cloud_correction import correct_cloud_bias
    from nightlights_econ.gdp_proxy import compute_all_metrics
    from nightlights_econ.core import RadianceSeries

    df = correct_cloud_bias(mock_radiance_data)
    config = LightingTechConfig(state="maharashtra", country_code="IND")
    df = apply_lighting_tech_adjustment(df, config)

    df = compute_all_metrics(
        df,
        base_year=2014,
        population_by_year=mock_population,
        ppp_factors=mock_ppp_factors,
        radiance_col="radiance_lta",
    )
    for col in ["gdp_proxy", "gdp_per_capita", "gdp_ppp_per_capita"]:
        assert col in df.columns
        assert not df[col].isna().all()
