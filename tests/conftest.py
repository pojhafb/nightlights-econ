"""Shared fixtures with mock GEE data."""

import numpy as np
import pandas as pd
import pytest

from nightlights_econ.core import CityDefinition, RadianceSeries


@pytest.fixture
def mock_radiance_data() -> pd.DataFrame:
    """12 years of monthly radiance for a city like Pune."""
    dates = pd.date_range("2014-01-01", "2026-03-01", freq="MS")
    np.random.seed(42)
    base = 5.0
    trend = np.linspace(0, 5, len(dates))
    seasonal = 0.5 * np.sin(2 * np.pi * np.arange(len(dates)) / 12)
    noise = np.random.normal(0, 0.3, len(dates))
    radiance = base + trend + seasonal + noise

    cf_obs = np.where(
        pd.DatetimeIndex(dates).month.isin([6, 7, 8, 9]),
        np.random.randint(1, 4, len(dates)),
        np.random.randint(8, 15, len(dates)),
    )
    monsoon_mask = pd.DatetimeIndex(dates).month.isin([6, 7, 8, 9])
    radiance[monsoon_mask] *= 0.8

    return pd.DataFrame({
        "date": dates,
        "year": dates.year,
        "month": dates.month,
        "radiance_raw": radiance,
        "cf_obs": cf_obs.astype(float),
    })


@pytest.fixture
def mock_population() -> dict[int, float]:
    return {yr: 5_000_000 + (yr - 2014) * 50_000 for yr in range(2014, 2027)}


@pytest.fixture
def mock_ppp_factors() -> dict[int, float]:
    return {yr: 18.0 + (yr - 2014) * 0.5 for yr in range(2014, 2027)}


@pytest.fixture
def pune_city() -> CityDefinition:
    return CityDefinition(
        name="Pune",
        country="India",
        admin1="Maharashtra",
        admin2="Pune",
        country_code="IND",
    )


@pytest.fixture
def full_series(mock_radiance_data, mock_population, mock_ppp_factors) -> RadianceSeries:
    """A complete RadianceSeries with all derived metrics pre-computed."""
    import matplotlib
    matplotlib.use("Agg")

    from nightlights_econ.cloud_correction import correct_cloud_bias
    from nightlights_econ.gdp_proxy import compute_all_metrics

    df = correct_cloud_bias(mock_radiance_data.copy())
    df = compute_all_metrics(
        df,
        base_year=2014,
        population_by_year=mock_population,
        ppp_factors=mock_ppp_factors,
    )

    return RadianceSeries(
        city="Pune",
        df=df,
        geometry_area_km2=331.0,
        population_by_year=mock_population,
        ppp_factors=mock_ppp_factors,
        metadata={"base_year": 2014, "start_year": 2014, "end_year": 2026},
    )
