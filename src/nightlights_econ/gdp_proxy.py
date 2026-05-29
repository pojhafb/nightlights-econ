"""GDP proxy estimation using the Henderson elasticity model.

Henderson, Vernon, Adam Storeygard, and David N. Weil.
"Measuring Economic Growth from Outer Space." (2012).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .utils import HENDERSON_ELASTICITY


def compute_gdp_proxy(
    df: pd.DataFrame,
    base_year: int,
    radiance_col: str = "radiance_corrected",
    elasticity: float = HENDERSON_ELASTICITY,
    gdp_proxy_col: str = "gdp_proxy",
) -> pd.DataFrame:
    """Compute GDP proxy index relative to base year = 100.

    Formula:
        GDP_proxy(t) = 100 * (radiance(t) / radiance_base)^elasticity

    Args:
        df: Monthly radiance DataFrame.
        base_year: Reference year; index will be 100 for this year.
        radiance_col: Column containing cloud-corrected radiance.
        elasticity: Henderson elasticity (default 0.88).
        gdp_proxy_col: Output column name.

    Returns:
        DataFrame with gdp_proxy_col added.
    """
    df = df.copy()
    base_mask = df["year"] == base_year
    base_radiance = df.loc[base_mask, radiance_col].mean()

    if base_radiance <= 0 or np.isnan(base_radiance):
        raise ValueError(
            f"Base year {base_year} has no valid radiance data in column '{radiance_col}'."
        )

    ratio = df[radiance_col] / base_radiance
    df[gdp_proxy_col] = np.where(ratio > 0, 100.0 * (ratio ** elasticity), np.nan)
    return df


def compute_gdp_per_capita(
    df: pd.DataFrame,
    population_by_year: dict[int, float],
    base_year: int,
    gdp_proxy_col: str = "gdp_proxy",
    gdp_per_capita_col: str = "gdp_per_capita",
) -> pd.DataFrame:
    """Compute GDP per capita index (GDP proxy / population), normalized to base year = 100.

    Args:
        df: DataFrame with gdp_proxy_col and 'year' column.
        population_by_year: Dict {year: population}.
        base_year: Reference year for normalization.
        gdp_proxy_col: Column holding GDP proxy index.
        gdp_per_capita_col: Output column name.

    Returns:
        DataFrame with gdp_per_capita_col added.
    """
    df = df.copy()
    df["_pop"] = df["year"].map(population_by_year)

    # Raw (not yet normalized) per-capita = proxy / population
    df["_pc_raw"] = df[gdp_proxy_col] / df["_pop"]

    base_mask = df["year"] == base_year
    base_pc = df.loc[base_mask, "_pc_raw"].mean()

    if base_pc <= 0 or np.isnan(base_pc):
        raise ValueError(
            f"Cannot compute per-capita index: base year {base_year} has no valid data."
        )

    df[gdp_per_capita_col] = df["_pc_raw"] / base_pc * 100.0
    df.drop(columns=["_pop", "_pc_raw"], inplace=True)
    return df


def compute_ppp_adjusted(
    df: pd.DataFrame,
    ppp_factors: dict[int, float],
    base_year: int,
    gdp_per_capita_col: str = "gdp_per_capita",
    gdp_ppp_per_capita_col: str = "gdp_ppp_per_capita",
) -> pd.DataFrame:
    """Compute PPP-adjusted GDP per capita index.

    Normalizes PPP factors to the base year so the index still starts at 100.

    Formula:
        GDP_PPP(t) = GDP_per_capita(t) / PPP_relative(t)
    where PPP_relative(t) = ppp_factor(t) / ppp_factor(base_year).

    Args:
        df: DataFrame with gdp_per_capita_col and 'year' column.
        ppp_factors: Dict {year: ppp_factor}.
        base_year: Reference year (PPP factor normalized to 1.0 here).
        gdp_per_capita_col: Input per-capita column.
        gdp_ppp_per_capita_col: Output PPP-adjusted column.

    Returns:
        DataFrame with gdp_ppp_per_capita_col added.
    """
    df = df.copy()
    base_ppp = ppp_factors.get(base_year, 1.0)
    if base_ppp == 0:
        base_ppp = 1.0

    def _relative_ppp(year: int) -> float:
        return ppp_factors.get(year, base_ppp) / base_ppp

    df["_ppp_rel"] = df["year"].map(_relative_ppp)
    df[gdp_ppp_per_capita_col] = df[gdp_per_capita_col] / df["_ppp_rel"]
    df.drop(columns=["_ppp_rel"], inplace=True)
    return df


def compute_all_metrics(
    df: pd.DataFrame,
    base_year: int,
    population_by_year: dict[int, float],
    ppp_factors: dict[int, float],
    radiance_col: str = "radiance_corrected",
    elasticity: float = HENDERSON_ELASTICITY,
) -> pd.DataFrame:
    """Compute GDP proxy, per-capita, and PPP-adjusted per-capita in one call.

    Args:
        df: Monthly radiance DataFrame.
        base_year: Reference year for all indices.
        population_by_year: Dict {year: population}.
        ppp_factors: Dict {year: ppp_factor}.
        radiance_col: Column holding corrected radiance.
        elasticity: Henderson elasticity.

    Returns:
        DataFrame with gdp_proxy, gdp_per_capita, gdp_ppp_per_capita columns added.
    """
    df = compute_gdp_proxy(df, base_year, radiance_col=radiance_col, elasticity=elasticity)
    df = compute_gdp_per_capita(df, population_by_year, base_year)
    df = compute_ppp_adjusted(df, ppp_factors, base_year)
    return df
