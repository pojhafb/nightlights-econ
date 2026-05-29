"""Shock analysis, growth decomposition, and city comparison."""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd


def shock_analysis(
    series,
    event_date: str,
    window_months: int = 12,
    metric: str = "gdp_proxy",
) -> dict:
    """Measure the impact of a shock event on a city's economic trajectory.

    Args:
        series: RadianceSeries instance.
        event_date: ISO date string for the shock event (e.g., "2025-04-22").
        window_months: Number of months before/after the event to analyse.
        metric: Column name in series.df to use (default "gdp_proxy").

    Returns:
        Dict with keys: pre_trend, post_trend, drop_pct, recovery_months,
        resilience_score, pre_df, post_df.
    """
    df = series.df.copy()
    df["date"] = pd.to_datetime(df["date"])
    event = pd.Timestamp(event_date)

    pre = df[(df["date"] >= event - pd.DateOffset(months=window_months)) & (df["date"] < event)].copy()
    post = df[(df["date"] >= event) & (df["date"] < event + pd.DateOffset(months=window_months))].copy()

    if pre.empty or post.empty:
        return {"error": "Not enough data around event_date"}

    pre_mean = pre[metric].mean()
    post_mean = post[metric].mean()
    drop_pct = (post_mean - pre_mean) / pre_mean * 100.0 if pre_mean != 0 else np.nan

    # Pre-event trend (slope of linear fit per month)
    pre["t"] = range(len(pre))
    pre_slope = float(np.polyfit(pre["t"], pre[metric].ffill(), 1)[0]) if len(pre) >= 2 else 0.0

    # Post-event trend
    post["t"] = range(len(post))
    post_slope = float(np.polyfit(post["t"], post[metric].ffill(), 1)[0]) if len(post) >= 2 else 0.0

    # Recovery: how many months after event to return to pre-event level
    recovery_months = None
    pre_level = pre[metric].iloc[-1] if len(pre) > 0 else pre_mean
    for i, val in enumerate(post[metric].values):
        if not np.isnan(val) and val >= pre_level:
            recovery_months = i + 1
            break

    # Resilience score: 0-100, higher is better
    # = 100 if no drop; scales down with drop size and recovery time
    if np.isnan(drop_pct) or drop_pct >= 0:
        resilience_score = 100.0
    else:
        severity_penalty = min(abs(drop_pct) * 2, 60)
        recovery_penalty = 0.0
        if recovery_months is not None:
            recovery_penalty = min(recovery_months * 2, 40)
        else:
            recovery_penalty = 40.0
        resilience_score = max(0.0, 100.0 - severity_penalty - recovery_penalty)

    return {
        "city": series.city,
        "event_date": event_date,
        "pre_mean": float(pre_mean),
        "post_mean": float(post_mean),
        "drop_pct": float(drop_pct),
        "pre_trend_per_month": float(pre_slope),
        "post_trend_per_month": float(post_slope),
        "recovery_months": recovery_months,
        "resilience_score": float(resilience_score),
        "pre_df": pre,
        "post_df": post,
    }


def growth_decomposition(
    series,
    metric: str = "gdp_per_capita",
    annualize: bool = True,
) -> pd.DataFrame:
    """Decompose growth into trend and cyclical components.

    Args:
        series: RadianceSeries instance.
        metric: Column in series.df to decompose.
        annualize: If True, compute annual CAGR summary.

    Returns:
        DataFrame with columns: year, month, value, trend, cyclical, yoy_growth_pct.
    """
    df = series.df[["date", "year", "month", metric]].copy().dropna(subset=[metric])
    df = df.sort_values("date").reset_index(drop=True)

    if len(df) < 12:
        df["trend"] = df[metric].rolling(3, center=True, min_periods=1).mean()
    else:
        df["trend"] = df[metric].rolling(12, center=True, min_periods=6).mean()

    df["cyclical"] = df[metric] - df["trend"]
    df["yoy_growth_pct"] = df[metric].pct_change(periods=12) * 100.0

    if annualize:
        annual = (
            df.groupby("year")[metric]
            .mean()
            .reset_index()
            .rename(columns={metric: "annual_mean"})
        )
        annual["annual_growth_pct"] = annual["annual_mean"].pct_change() * 100.0
        df = df.merge(annual[["year", "annual_growth_pct"]], on="year", how="left")

    return df


def compare_cities(
    series_list: list,
    metric: str = "gdp_per_capita",
    start_year: Optional[int] = None,
    end_year: Optional[int] = None,
) -> pd.DataFrame:
    """Compare multiple cities on a common metric, aligned to base year = 100.

    Args:
        series_list: List of RadianceSeries instances.
        metric: Column to compare.
        start_year: Filter to this start year (default: earliest common year).
        end_year: Filter to this end year (default: latest common year).

    Returns:
        Wide-format DataFrame with date as index and city names as columns.
    """
    frames = []
    for s in series_list:
        df = s.df[["date", "year", metric]].copy()
        df = df.rename(columns={metric: s.city})
        frames.append(df.set_index("date"))

    combined = pd.concat([f.drop(columns=["year"], errors="ignore") for f in frames], axis=1)

    if start_year:
        combined = combined[combined.index.year >= start_year]
    if end_year:
        combined = combined[combined.index.year <= end_year]

    return combined.sort_index()


def compute_correlation_matrix(
    series_list: list,
    metric: str = "gdp_per_capita",
) -> pd.DataFrame:
    """Compute pairwise Pearson correlation of the chosen metric across cities.

    Args:
        series_list: List of RadianceSeries instances.
        metric: Column to correlate.

    Returns:
        Correlation matrix as a DataFrame.
    """
    wide = compare_cities(series_list, metric=metric)
    return wide.corr(method="pearson")


def total_growth_pct(series, metric: str = "gdp_per_capita") -> float:
    """Compute total percentage growth from first to last valid observation.

    Args:
        series: RadianceSeries instance.
        metric: Column in series.df.

    Returns:
        Percentage growth (e.g., 45.3 means +45.3%).
    """
    df = series.df[[metric]].dropna()
    if len(df) < 2:
        return np.nan
    first = df.iloc[0].values[0]
    last = df.iloc[-1].values[0]
    if first == 0:
        return np.nan
    return float((last - first) / first * 100.0)
