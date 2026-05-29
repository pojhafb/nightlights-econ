"""City and country ranking system."""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

import numpy as np
import pandas as pd

from .analysis import total_growth_pct, shock_analysis

if TYPE_CHECKING:
    from .core import CityDefinition, RadianceSeries
    import matplotlib.pyplot as plt


def rank_cities(
    series_list: list,
    metric: str = "per_capita_growth",
    top_n: int = 5,
    bottom_n: int = 5,
) -> pd.DataFrame:
    """Rank cities by a summary metric, returning top N and bottom N.

    Args:
        series_list: List of RadianceSeries instances.
        metric: One of "per_capita_growth", "total_growth", "ppp_per_capita",
                or "resilience" (requires shock_results in metadata).
        top_n: Number of top cities to include.
        bottom_n: Number of bottom cities to include.

    Returns:
        DataFrame with columns: city, metric_value, rank, tier.
    """
    records = []
    for s in series_list:
        val = _compute_metric(s, metric)
        pop = _latest_population(s)
        records.append({
            "city": s.city,
            "value": val,
            "population": pop,
        })

    df = pd.DataFrame(records).dropna(subset=["value"])
    df = df.sort_values("value", ascending=False).reset_index(drop=True)
    df["rank"] = df.index + 1

    n = len(df)
    top_idx = set(range(min(top_n, n)))
    bottom_idx = set(range(max(0, n - bottom_n), n))
    selected_idx = sorted(top_idx | bottom_idx)

    result = df.iloc[selected_idx].copy()
    result["tier"] = result["rank"].apply(
        lambda r: "top" if r <= top_n else "bottom"
    )
    result.rename(columns={"value": metric}, inplace=True)
    return result.reset_index(drop=True)


def _compute_metric(series, metric: str) -> float:
    """Extract a scalar metric from a RadianceSeries."""
    if metric == "per_capita_growth":
        return total_growth_pct(series, "gdp_per_capita")
    elif metric == "total_growth":
        return total_growth_pct(series, "gdp_proxy")
    elif metric == "ppp_per_capita":
        return total_growth_pct(series, "gdp_ppp_per_capita")
    elif metric == "resilience":
        shock_results = series.metadata.get("shock_results")
        if shock_results:
            return shock_results.get("resilience_score", np.nan)
        return np.nan
    else:
        # Treat as a direct column name — return total growth on it
        if metric in series.df.columns:
            return total_growth_pct(series, metric)
        return np.nan


def _latest_population(series) -> float:
    if not series.population_by_year:
        return np.nan
    latest_year = max(series.population_by_year.keys())
    return float(series.population_by_year[latest_year])


def rank_country(
    country: str,
    admin1_list: Optional[list[str]] = None,
    start_year: int = 2014,
    end_year: int = 2026,
    top_n: int = 5,
    bottom_n: int = 5,
    engine=None,
) -> pd.DataFrame:
    """Analyze ALL districts in a country and rank them.

    Requires an initialized NighttimeLightsEngine.

    Args:
        country: Country name (e.g., "India").
        admin1_list: Optional list of states to restrict analysis to.
        start_year: First analysis year.
        end_year: Last analysis year.
        top_n: Number of top districts.
        bottom_n: Number of bottom districts.
        engine: NighttimeLightsEngine instance (must be pre-authenticated).

    Returns:
        DataFrame with ranked districts.
    """
    if engine is None:
        raise ValueError(
            "rank_country requires a NighttimeLightsEngine instance. "
            "Initialize one and pass it as the `engine` parameter."
        )

    from .core import CityDefinition

    try:
        import ee
    except ImportError:
        raise ImportError("earthengine-api required for rank_country.")

    engine._init_ee()
    ee_mod = engine._ee

    gaul = ee_mod.FeatureCollection("FAO/GAUL/2015/level2")
    filtered = gaul.filter(ee_mod.Filter.eq("ADM0_NAME", country))
    if admin1_list:
        filtered = filtered.filter(ee_mod.Filter.inList("ADM1_NAME", admin1_list))

    district_info = filtered.select(["ADM1_NAME", "ADM2_NAME"]).getInfo()
    cities = []
    for feat in district_info.get("features", []):
        props = feat.get("properties", {})
        admin1 = props.get("ADM1_NAME", "")
        admin2 = props.get("ADM2_NAME", "")
        if admin2:
            cities.append(CityDefinition(
                name=admin2,
                country=country,
                admin1=admin1,
                admin2=admin2,
            ))

    if not cities:
        raise RuntimeError(f"No districts found for {country}.")

    series_list = engine.analyze_many(cities, start_year=start_year, end_year=end_year)
    return rank_cities(series_list, top_n=top_n, bottom_n=bottom_n)


def rank_region(
    cities: list,
    metric: str = "per_capita_growth",
    top_n: int = 5,
    bottom_n: int = 5,
    engine=None,
    start_year: int = 2014,
    end_year: int = 2026,
) -> tuple[pd.DataFrame, "plt.Figure"]:
    """Analyze and rank a user-specified list of cities, returning results + chart.

    Args:
        cities: List of CityDefinition instances.
        metric: Ranking metric.
        top_n: Top N cities.
        bottom_n: Bottom N cities.
        engine: NighttimeLightsEngine instance.
        start_year: First year.
        end_year: Last year.

    Returns:
        Tuple of (rankings DataFrame, matplotlib Figure).
    """
    if engine is None:
        raise ValueError("rank_region requires a NighttimeLightsEngine instance.")

    series_list = engine.analyze_many(cities, start_year=start_year, end_year=end_year)
    df = rank_cities(series_list, metric=metric, top_n=top_n, bottom_n=bottom_n)

    from .plotting import plot_rankings
    fig = plot_rankings(
        df.rename(columns={metric: "value"}).assign(**{metric: df[metric]}),
        metric=metric,
        title=f"Region Rankings: {metric.replace('_', ' ').title()}",
    )
    return df, fig
