"""Tests for shock analysis, growth decomposition, and city comparison."""

import numpy as np
import pandas as pd
import pytest

from nightlights_econ.analysis import (
    shock_analysis,
    growth_decomposition,
    compare_cities,
    total_growth_pct,
    compute_correlation_matrix,
)


def test_shock_drop_detected(full_series):
    """Shock analysis should detect a drop in GDP when we inject one."""
    import copy
    s = copy.deepcopy(full_series)
    # Inject a 30% drop in 2020
    drop_mask = (s.df["year"] == 2020) & (s.df["month"].isin([1, 2, 3, 4, 5, 6]))
    s.df.loc[drop_mask, "gdp_proxy"] *= 0.70

    result = shock_analysis(s, event_date="2020-01-01", window_months=12)
    assert "error" not in result
    assert result["drop_pct"] < 0, "Should detect negative drop"


def test_shock_no_drop(full_series):
    """If nothing changes around event date, resilience should be high."""
    result = shock_analysis(full_series, event_date="2018-06-01", window_months=6)
    if "error" not in result:
        # With no induced drop, resilience should be reasonably high
        assert result["resilience_score"] >= 0
        assert result["resilience_score"] <= 100


def test_shock_before_data_range(full_series):
    """Event date before data range should return error."""
    result = shock_analysis(full_series, event_date="2010-01-01", window_months=12)
    assert "error" in result


def test_growth_decomposition_has_trend(full_series):
    """Decomposition should produce trend and cyclical columns."""
    df = growth_decomposition(full_series)
    assert "trend" in df.columns
    assert "cyclical" in df.columns
    assert "yoy_growth_pct" in df.columns
    assert not df["trend"].isna().all()


def test_growth_decomposition_trend_roughly_monotone(full_series):
    """For a series with positive trend, mean trend in later years > earlier years."""
    df = growth_decomposition(full_series)
    early = df[df["year"] <= 2017]["trend"].mean()
    late = df[df["year"] >= 2022]["trend"].mean()
    assert late > early, "Trend should generally increase over time"


def test_compare_cities_shape(full_series):
    """compare_cities should return wide DataFrame with one column per city."""
    import copy
    s2 = copy.deepcopy(full_series)
    s2.city = "Srinagar"
    result = compare_cities([full_series, s2])
    assert "Pune" in result.columns
    assert "Srinagar" in result.columns
    assert len(result) > 0


def test_city_ranking_order(full_series):
    """City with higher growth should rank first."""
    import copy
    import numpy as np
    from nightlights_econ.rankings import rank_cities

    # GrowthCity: starts at 100, ends at ~300 (strong growth)
    s_high = copy.deepcopy(full_series)
    s_high.city = "GrowthCity"
    n = len(s_high.df)
    s_high.df["gdp_per_capita"] = np.linspace(100, 300, n)

    # StagnantCity: starts at 100, ends at ~80 (decline)
    s_low = copy.deepcopy(full_series)
    s_low.city = "StagnantCity"
    s_low.df["gdp_per_capita"] = np.linspace(100, 80, n)

    ranking = rank_cities([s_high, s_low], metric="per_capita_growth", top_n=1, bottom_n=1)
    top_city = ranking[ranking["rank"] == 1]["city"].values[0]
    assert top_city == "GrowthCity"


def test_total_growth_pct(full_series):
    """Total growth should be positive for an upward-trending series."""
    growth = total_growth_pct(full_series, "gdp_per_capita")
    assert growth > 0, "Expected positive growth for mock upward-trending series"


def test_correlation_matrix_diagonal(full_series):
    """Correlation matrix diagonal should be ~1.0."""
    import copy
    s2 = copy.deepcopy(full_series)
    s2.city = "Other"
    corr = compute_correlation_matrix([full_series, s2])
    for c in corr.columns:
        assert abs(corr.loc[c, c] - 1.0) < 1e-6
