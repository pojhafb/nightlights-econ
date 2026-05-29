"""Tests for plotting functions — verify figures are returned, no crashes."""

import matplotlib
matplotlib.use("Agg")

import copy
import os
import tempfile

import numpy as np
import pandas as pd
import pytest

from nightlights_econ.plotting import (
    plot_gdp_population,
    plot_per_capita_gdp,
    plot_ppp_adjusted,
    plot_raw_radiance,
    plot_city_comparison,
    plot_rankings,
    plot_shock_resilience,
    plot_city_report,
    plot_comparison_report,
)


def test_plot_gdp_population_returns_figure(full_series):
    fig = plot_gdp_population(full_series)
    assert fig is not None
    assert hasattr(fig, "savefig")
    matplotlib.pyplot.close(fig)


def test_plot_per_capita_gdp_returns_figure(full_series):
    fig = plot_per_capita_gdp(full_series)
    assert fig is not None
    matplotlib.pyplot.close(fig)


def test_plot_ppp_adjusted_returns_figure(full_series):
    fig = plot_ppp_adjusted(full_series)
    assert fig is not None
    matplotlib.pyplot.close(fig)


def test_plot_raw_radiance_returns_figure(full_series):
    fig = plot_raw_radiance(full_series)
    assert fig is not None
    matplotlib.pyplot.close(fig)


def test_plot_city_comparison_returns_figure(full_series):
    s2 = copy.deepcopy(full_series)
    s2.city = "Srinagar"
    fig = plot_city_comparison([full_series, s2])
    assert fig is not None
    matplotlib.pyplot.close(fig)


def test_plot_rankings_returns_figure():
    import pandas as pd
    df = pd.DataFrame({
        "city": ["CityA", "CityB", "CityC", "CityD", "CityE"],
        "per_capita_growth": [45.0, 30.0, 20.0, 10.0, -5.0],
        "population": [1e6, 2e6, 1.5e6, 0.5e6, 3e6],
    })
    fig = plot_rankings(df, metric="per_capita_growth")
    assert fig is not None
    matplotlib.pyplot.close(fig)


def test_plot_shock_resilience_returns_figure(full_series):
    from nightlights_econ.analysis import shock_analysis
    result = shock_analysis(full_series, event_date="2020-01-01", window_months=12)
    if "error" not in result:
        result["city"] = full_series.city
        fig = plot_shock_resilience([result], event_name="Test Event")
        assert fig is not None
        matplotlib.pyplot.close(fig)


def test_plot_with_events(full_series):
    events = [{"date": "2020-01-01", "label": "Test Event"}]
    fig = plot_gdp_population(full_series, events=events)
    assert fig is not None
    matplotlib.pyplot.close(fig)


def test_save_to_file(full_series):
    """Verify save_path writes a real file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "test_chart.png")
        fig = plot_gdp_population(full_series, save_path=path)
        assert os.path.exists(path)
        assert os.path.getsize(path) > 1000
        matplotlib.pyplot.close(fig)


def test_plot_city_report_saves_files(full_series):
    """plot_city_report should create multiple PNG files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        figs = plot_city_report(full_series, save_dir=tmpdir)
        assert len(figs) == 4
        pngs = list(Path(tmpdir).glob("*.png"))
        assert len(pngs) == 4
        for fig in figs.values():
            matplotlib.pyplot.close(fig)


def test_plot_comparison_report_saves_files(full_series):
    """plot_comparison_report should create at least one PNG."""
    s2 = copy.deepcopy(full_series)
    s2.city = "Leh"
    with tempfile.TemporaryDirectory() as tmpdir:
        figs = plot_comparison_report([full_series, s2], save_dir=tmpdir)
        assert len(figs) >= 1
        pngs = list(Path(tmpdir).glob("*.png"))
        assert len(pngs) >= 1
        for fig in figs.values():
            matplotlib.pyplot.close(fig)


def test_single_month_does_not_crash(mock_population, mock_ppp_factors):
    """A series with only one month should not raise an exception."""
    from nightlights_econ.core import RadianceSeries
    df = pd.DataFrame({
        "date": [pd.Timestamp("2020-01-01")],
        "year": [2020],
        "month": [1],
        "radiance_raw": [5.0],
        "radiance_corrected": [5.0],
        "cf_obs": [10.0],
        "gdp_proxy": [100.0],
        "gdp_per_capita": [100.0],
        "gdp_ppp_per_capita": [100.0],
    })
    s = RadianceSeries(
        city="SingleMonth",
        df=df,
        geometry_area_km2=100.0,
        population_by_year=mock_population,
        ppp_factors=mock_ppp_factors,
        metadata={"base_year": 2020},
    )
    fig = plot_gdp_population(s)
    assert fig is not None
    matplotlib.pyplot.close(fig)


def test_all_nan_does_not_crash(mock_population, mock_ppp_factors):
    """A series with all-NaN GDP values should not crash plotting."""
    from nightlights_econ.core import RadianceSeries
    import numpy as np
    dates = pd.date_range("2014-01-01", periods=12, freq="MS")
    df = pd.DataFrame({
        "date": dates,
        "year": dates.year,
        "month": dates.month,
        "radiance_raw": np.full(12, np.nan),
        "radiance_corrected": np.full(12, np.nan),
        "cf_obs": np.full(12, np.nan),
        "gdp_proxy": np.full(12, np.nan),
        "gdp_per_capita": np.full(12, np.nan),
        "gdp_ppp_per_capita": np.full(12, np.nan),
    })
    s = RadianceSeries(
        city="NaNCity",
        df=df,
        geometry_area_km2=100.0,
        population_by_year=mock_population,
        ppp_factors=mock_ppp_factors,
        metadata={"base_year": 2014},
    )
    try:
        fig = plot_gdp_population(s)
        matplotlib.pyplot.close(fig)
    except Exception as exc:
        pytest.fail(f"plot_gdp_population crashed on all-NaN series: {exc}")


# Make Path available in module scope for test_plot_city_report_saves_files
from pathlib import Path
import matplotlib.pyplot
