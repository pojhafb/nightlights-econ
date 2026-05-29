"""Publication-quality chart generation (Economist/FT style).

All plot functions:
- Accept save_path: Optional[str] to save to file.
- Return the matplotlib Figure object.
- Work without display (Agg backend safe).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import matplotlib
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
import seaborn as sns

from .utils import MONSOON_MONTHS, safe_save

# ---------------------------------------------------------------------------
# Style constants
# ---------------------------------------------------------------------------
PALETTE = ["#1B4F72", "#E74C3C", "#F39C12", "#27AE60", "#8E44AD", "#2C3E50"]
BACKGROUND = "#FAFAFA"
GRID_COLOR = "#E0E0E0"
SPINE_COLOR = "#CCCCCC"
ANNOTATION_COLOR = "#555555"
SOURCE_TEXT = "Source: NASA VIIRS DNB / NOAA / GHS-POP / World Bank"
FONT_FAMILY = "DejaVu Sans"

_STYLE_APPLIED = False


def _apply_style() -> None:
    global _STYLE_APPLIED
    if _STYLE_APPLIED:
        return
    plt.rcParams.update({
        "font.family": FONT_FAMILY,
        "font.size": 11,
        "axes.facecolor": BACKGROUND,
        "figure.facecolor": BACKGROUND,
        "axes.grid": True,
        "axes.grid.axis": "y",
        "grid.color": GRID_COLOR,
        "grid.linewidth": 0.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.spines.left": True,
        "axes.spines.bottom": True,
        "axes.edgecolor": SPINE_COLOR,
        "xtick.direction": "out",
        "ytick.direction": "out",
        "xtick.major.size": 4,
        "ytick.major.size": 0,
        "legend.frameon": False,
        "legend.fontsize": 10,
        "figure.dpi": 150,
    })
    _STYLE_APPLIED = True


def _add_source(ax: plt.Axes, text: str = SOURCE_TEXT) -> None:
    ax.annotate(
        text,
        xy=(0, -0.12),
        xycoords="axes fraction",
        fontsize=8,
        color=ANNOTATION_COLOR,
        ha="left",
    )


def _shade_monsoon(ax: plt.Axes, df: pd.DataFrame, alpha: float = 0.08) -> None:
    """Shade monsoon months (Jun-Sep) in a time-series axis."""
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    for _, row in df[df["month"].isin(MONSOON_MONTHS)].iterrows():
        start = row["date"]
        end = start + pd.DateOffset(months=1)
        ax.axvspan(start, end, alpha=alpha, color="#4A90E2", zorder=0)


def _annotate_events(
    ax: plt.Axes,
    events: Optional[list[dict]],
    y_pos: float = 0.95,
) -> None:
    """Draw vertical lines and labels for notable events.

    Args:
        ax: Matplotlib axis.
        events: List of {"date": "YYYY-MM-DD", "label": "Event name"}.
        y_pos: Fractional y position for label (in axis coordinates).
    """
    if not events:
        return
    for evt in events:
        date = pd.Timestamp(evt["date"])
        ax.axvline(date, color="#E74C3C", linewidth=1.2, linestyle="--", alpha=0.7, zorder=3)
        ax.annotate(
            evt["label"],
            xy=(date, y_pos),
            xycoords=("data", "axes fraction"),
            fontsize=8,
            color="#E74C3C",
            rotation=90,
            va="top",
            ha="right",
        )


def plot_gdp_population(
    series,
    base_year: Optional[int] = None,
    events: Optional[list[dict]] = None,
    save_path: Optional[str] = None,
) -> plt.Figure:
    """Chart 1: Dual-axis GDP proxy + Population Growth.

    Args:
        series: RadianceSeries instance.
        base_year: Reference year for normalisation (default: series.base_year).
        events: List of {"date": ..., "label": ...} annotations.
        save_path: If provided, save figure to this path.

    Returns:
        matplotlib Figure.
    """
    _apply_style()
    base_year = base_year or series.base_year
    df = series.df.copy()
    df["date"] = pd.to_datetime(df["date"])
    annual = series.annual_df

    fig, ax1 = plt.subplots(figsize=(12, 7))
    ax2 = ax1.twinx()

    # GDP proxy
    ax1.plot(
        df["date"], df["gdp_proxy"],
        color=PALETTE[0], linewidth=2.2, label="GDP Proxy (index)",
        zorder=4,
    )

    # Population (millions)
    pop_series = [series.population_by_year.get(yr, np.nan) / 1e6
                  for yr in df["year"]]
    ax2.plot(
        df["date"], pop_series,
        color=PALETTE[2], linewidth=1.8, linestyle="--",
        label="Population (millions)", alpha=0.85, zorder=3,
    )

    _shade_monsoon(ax1, df)
    _annotate_events(ax1, events)

    ax1.set_ylabel("GDP Proxy Index (base year = 100)", color=PALETTE[0], fontsize=11)
    ax2.set_ylabel("Population (millions)", color=PALETTE[2], fontsize=11)
    ax1.tick_params(axis="y", labelcolor=PALETTE[0])
    ax2.tick_params(axis="y", labelcolor=PALETTE[2])
    ax2.grid(False)

    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax1.xaxis.set_major_locator(mdates.YearLocator(2))
    fig.autofmt_xdate()

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")

    ax1.set_title(
        f"{series.city}: GDP Growth vs Population Growth (VIIRS Nighttime Lights)",
        fontsize=14, fontweight="bold", pad=15,
    )

    monsoon_patch = mpatches.Patch(color="#4A90E2", alpha=0.2, label="Monsoon (cloud correction)")
    ax1.legend(lines1 + lines2 + [monsoon_patch],
               labels1 + labels2 + ["Monsoon (cloud correction)"],
               loc="upper left", fontsize=9)

    _add_source(ax1)
    fig.tight_layout()
    safe_save(fig, save_path)
    return fig


def plot_per_capita_gdp(
    series,
    base_year: Optional[int] = None,
    events: Optional[list[dict]] = None,
    save_path: Optional[str] = None,
) -> plt.Figure:
    """Chart 2: Per-Capita GDP Proxy with YoY growth bars.

    Args:
        series: RadianceSeries instance.
        base_year: Reference year.
        events: Annotation events.
        save_path: Optional file path.

    Returns:
        matplotlib Figure.
    """
    _apply_style()
    base_year = base_year or series.base_year
    df = series.df.copy()
    df["date"] = pd.to_datetime(df["date"])

    yoy = df["gdp_per_capita"].pct_change(periods=12) * 100

    fig, (ax_top, ax_bot) = plt.subplots(
        2, 1, figsize=(12, 8), gridspec_kw={"height_ratios": [3, 1]}, sharex=True
    )

    # Rolling std confidence band
    rolling_std = df["gdp_per_capita"].rolling(12, min_periods=3).std()
    ax_top.fill_between(
        df["date"],
        df["gdp_per_capita"] - rolling_std,
        df["gdp_per_capita"] + rolling_std,
        alpha=0.15, color=PALETTE[0], label="±1 std band",
    )
    ax_top.plot(
        df["date"], df["gdp_per_capita"],
        color=PALETTE[0], linewidth=2.2, label="GDP per capita (index)",
    )
    ax_top.axhline(100, color=SPINE_COLOR, linewidth=1.0, linestyle="--", zorder=0)

    _shade_monsoon(ax_top, df)
    _annotate_events(ax_top, events)

    # YoY growth bars
    positive = yoy.clip(lower=0)
    negative = yoy.clip(upper=0)
    ax_bot.bar(df["date"], positive, width=25, color=PALETTE[3], alpha=0.8, label="YoY growth (%)")
    ax_bot.bar(df["date"], negative, width=25, color=PALETTE[1], alpha=0.8)
    ax_bot.axhline(0, color=SPINE_COLOR, linewidth=0.8)
    ax_bot.set_ylabel("YoY %", fontsize=9)

    ax_top.set_ylabel("GDP per Capita Index (base year = 100)", fontsize=11)
    ax_top.legend(fontsize=9, loc="upper left")
    ax_top.set_title(
        f"{series.city}: Real GDP Per Capita (Population-Adjusted)",
        fontsize=14, fontweight="bold", pad=15,
    )

    ax_bot.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax_bot.xaxis.set_major_locator(mdates.YearLocator(2))
    fig.autofmt_xdate()
    _add_source(ax_bot)
    fig.tight_layout()
    safe_save(fig, save_path)
    return fig


def plot_ppp_adjusted(
    series,
    base_year: Optional[int] = None,
    save_path: Optional[str] = None,
) -> plt.Figure:
    """Chart 3: Nominal vs PPP-adjusted per-capita GDP.

    Args:
        series: RadianceSeries instance.
        base_year: Reference year.
        save_path: Optional file path.

    Returns:
        matplotlib Figure.
    """
    _apply_style()
    df = series.df.copy()
    df["date"] = pd.to_datetime(df["date"])

    fig, ax = plt.subplots(figsize=(12, 7))
    ax.plot(df["date"], df["gdp_per_capita"], color=PALETTE[0], linewidth=2.2,
            label="Nominal GDP per capita (index)")
    ax.plot(df["date"], df["gdp_ppp_per_capita"], color=PALETTE[1], linewidth=2.2,
            linestyle="--", label="PPP-adjusted GDP per capita (index)")

    ax.fill_between(
        df["date"],
        df["gdp_per_capita"], df["gdp_ppp_per_capita"],
        alpha=0.08, color=PALETTE[2], label="Divergence (inflation/FX effect)",
    )

    ax.axhline(100, color=SPINE_COLOR, linewidth=1.0, linestyle=":", zorder=0)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.xaxis.set_major_locator(mdates.YearLocator(2))
    fig.autofmt_xdate()

    ax.set_ylabel("Index (base year = 100)", fontsize=11)
    ax.legend(fontsize=9)
    ax.set_title(
        f"{series.city}: PPP-Adjusted GDP Per Capita",
        fontsize=14, fontweight="bold", pad=15,
    )
    _add_source(ax)
    fig.tight_layout()
    safe_save(fig, save_path)
    return fig


def plot_raw_radiance(
    series,
    save_path: Optional[str] = None,
) -> plt.Figure:
    """Chart 4: Raw vs corrected radiance + cloud-free observation count.

    Args:
        series: RadianceSeries instance.
        save_path: Optional file path.

    Returns:
        matplotlib Figure.
    """
    _apply_style()
    df = series.df.copy()
    df["date"] = pd.to_datetime(df["date"])

    fig, (ax_top, ax_bot) = plt.subplots(
        2, 1, figsize=(12, 8), gridspec_kw={"height_ratios": [3, 1]}, sharex=True
    )

    ax_top.plot(df["date"], df["radiance_raw"], color="#AAAAAA", linewidth=1.2,
                label="Raw radiance", alpha=0.7)
    ax_top.plot(df["date"], df["radiance_corrected"], color=PALETTE[0], linewidth=2.0,
                label="Cloud-corrected radiance")

    _shade_monsoon(ax_top, df)

    ax_top.set_ylabel("Radiance (nW/cm²/sr)", fontsize=11)
    ax_top.legend(fontsize=9)
    ax_top.set_title(
        f"{series.city}: Monthly Nighttime Radiance (VIIRS DNB)",
        fontsize=14, fontweight="bold", pad=15,
    )

    # Cloud-free obs bar chart (only when data is available — not for DMSP annual)
    cf_series = pd.to_numeric(df["cf_obs"], errors="coerce")
    if cf_series.notna().any():
        ax_bot.bar(df["date"], cf_series.fillna(0), width=25, color=PALETTE[0], alpha=0.7,
                   label="Cloud-free obs")
        ax_bot.axhline(8, color=PALETTE[1], linewidth=1.0, linestyle="--", alpha=0.8,
                       label="Correction threshold (8)")
        ax_bot.legend(fontsize=8)
    else:
        ax_bot.text(0.5, 0.5, "Cloud-free obs not available\n(DMSP-OLS annual composite)",
                    ha="center", va="center", transform=ax_bot.transAxes,
                    fontsize=9, color=ANNOTATION_COLOR)
    ax_bot.set_ylabel("CF obs/month", fontsize=9)

    ax_bot.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax_bot.xaxis.set_major_locator(mdates.YearLocator(2))
    fig.autofmt_xdate()
    _add_source(ax_bot)
    fig.tight_layout()
    safe_save(fig, save_path)
    return fig


def plot_city_comparison(
    series_list: list,
    metric: str = "gdp_per_capita",
    save_path: Optional[str] = None,
) -> plt.Figure:
    """Chart 5: City comparison dashboard (2×2 subplots).

    Args:
        series_list: List of RadianceSeries instances.
        metric: Metric to compare in time-series panels.
        save_path: Optional file path.

    Returns:
        matplotlib Figure.
    """
    _apply_style()
    from .analysis import total_growth_pct

    colors = [PALETTE[i % len(PALETTE)] for i in range(len(series_list))]
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    ax_rad, ax_pc = axes[0]
    ax_rad_rank, ax_pc_rank = axes[1]

    # Top-left: radiance growth indexed
    for i, s in enumerate(series_list):
        df = s.df.copy()
        df["date"] = pd.to_datetime(df["date"])
        ax_rad.plot(df["date"], df["gdp_proxy"], color=colors[i],
                    linewidth=1.8, label=s.city)
    ax_rad.axhline(100, color=SPINE_COLOR, linewidth=0.8, linestyle="--")
    ax_rad.set_title("GDP Proxy (base year = 100)", fontsize=11, fontweight="bold")
    ax_rad.legend(fontsize=9)
    ax_rad.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    # Top-right: per-capita growth
    for i, s in enumerate(series_list):
        df = s.df.copy()
        df["date"] = pd.to_datetime(df["date"])
        ax_pc.plot(df["date"], df[metric], color=colors[i],
                   linewidth=1.8, label=s.city)
    ax_pc.axhline(100, color=SPINE_COLOR, linewidth=0.8, linestyle="--")
    ax_pc.set_title("GDP Per Capita (base year = 100)", fontsize=11, fontweight="bold")
    ax_pc.legend(fontsize=9)
    ax_pc.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    # Bottom-left: total radiance growth % ranked
    city_names = [s.city for s in series_list]
    rad_growths = [total_growth_pct(s, "gdp_proxy") for s in series_list]
    sorted_idx = np.argsort(rad_growths)
    ax_rad_rank.barh(
        [city_names[i] for i in sorted_idx],
        [rad_growths[i] for i in sorted_idx],
        color=[colors[i] for i in sorted_idx],
    )
    ax_rad_rank.axvline(0, color=SPINE_COLOR, linewidth=0.8)
    ax_rad_rank.set_xlabel("Total GDP Proxy Growth (%)", fontsize=10)
    ax_rad_rank.set_title("Total GDP Growth Ranking", fontsize=11, fontweight="bold")

    # Bottom-right: per-capita growth % ranked
    pc_growths = [total_growth_pct(s, metric) for s in series_list]
    sorted_idx = np.argsort(pc_growths)
    ax_pc_rank.barh(
        [city_names[i] for i in sorted_idx],
        [pc_growths[i] for i in sorted_idx],
        color=[colors[i] for i in sorted_idx],
    )
    ax_pc_rank.axvline(0, color=SPINE_COLOR, linewidth=0.8)
    ax_pc_rank.set_xlabel("Total Per-Capita Growth (%)", fontsize=10)
    ax_pc_rank.set_title("Per-Capita Growth Ranking", fontsize=11, fontweight="bold")

    for ax in axes.flat:
        ax.grid(True, axis="y", color=GRID_COLOR, linewidth=0.7)

    fig.suptitle(
        f"City Comparison Dashboard: {', '.join(city_names)}",
        fontsize=15, fontweight="bold", y=1.01,
    )
    _add_source(axes[1][0])
    fig.tight_layout()
    safe_save(fig, save_path)
    return fig


def plot_rankings(
    rankings_df: pd.DataFrame,
    metric: str = "per_capita_growth",
    title: str = "City Rankings",
    save_path: Optional[str] = None,
) -> plt.Figure:
    """Chart 6: Rankings chart — top and bottom cities.

    Args:
        rankings_df: DataFrame with 'city', metric column, and optionally 'population'.
        metric: Column to rank by.
        title: Chart title.
        save_path: Optional file path.

    Returns:
        matplotlib Figure.
    """
    _apply_style()
    df = rankings_df.copy().sort_values(metric)
    values = df[metric].values
    cities = df["city"].values

    median_val = float(np.nanmedian(values))

    def _color(v: float) -> str:
        if np.isnan(v):
            return "#AAAAAA"
        if v > median_val * 1.15:
            return PALETTE[3]   # green
        if v < median_val * 0.85:
            return PALETTE[1]   # red
        return PALETTE[2]       # amber

    bar_colors = [_color(v) for v in values]

    fig, ax = plt.subplots(figsize=(12, max(6, len(df) * 0.45)))
    bars = ax.barh(cities, values, color=bar_colors, height=0.65)

    ax.axvline(median_val, color=SPINE_COLOR, linewidth=1.2, linestyle="--",
               label=f"Median ({median_val:.1f}%)")
    ax.set_xlabel(f"{metric.replace('_', ' ').title()} (%)", fontsize=11)
    ax.legend(fontsize=9)
    ax.set_title(title, fontsize=14, fontweight="bold", pad=15)

    # Annotate population if present
    if "population" in df.columns:
        for bar, (_, row) in zip(bars, df.iterrows()):
            pop = row.get("population", np.nan)
            if not np.isnan(pop):
                ax.annotate(
                    f"{pop/1e6:.1f}M",
                    xy=(bar.get_width(), bar.get_y() + bar.get_height() / 2),
                    xytext=(4, 0), textcoords="offset points",
                    fontsize=8, va="center", color=ANNOTATION_COLOR,
                )

    green_patch = mpatches.Patch(color=PALETTE[3], label="Above median")
    amber_patch = mpatches.Patch(color=PALETTE[2], label="Near median")
    red_patch = mpatches.Patch(color=PALETTE[1], label="Below median")
    ax.legend(handles=[green_patch, amber_patch, red_patch], fontsize=9, loc="lower right")

    _add_source(ax)
    fig.tight_layout()
    safe_save(fig, save_path)
    return fig


def plot_shock_resilience(
    shock_results: list[dict],
    event_name: str = "Event",
    metric: str = "gdp_proxy",
    save_path: Optional[str] = None,
) -> plt.Figure:
    """Chart 7: Shock resilience comparison across cities.

    Args:
        shock_results: List of dicts returned by analysis.shock_analysis().
        event_name: Name of the shock event (for title/annotation).
        metric: Metric used in shock analysis.
        save_path: Optional file path.

    Returns:
        matplotlib Figure.
    """
    _apply_style()
    colors = [PALETTE[i % len(PALETTE)] for i in range(len(shock_results))]

    fig, ax = plt.subplots(figsize=(13, 7))

    for i, result in enumerate(shock_results):
        if "error" in result:
            continue
        pre = result["pre_df"].copy()
        post = result["post_df"].copy()
        pre["date"] = pd.to_datetime(pre["date"])
        post["date"] = pd.to_datetime(post["date"])
        city = result["city"]
        score = result["resilience_score"]

        combined = pd.concat([pre, post]).sort_values("date")
        ax.plot(combined["date"], combined[metric], color=colors[i],
                linewidth=2.0, label=f"{city} (resilience: {score:.0f}/100)")

    # Shade pre vs post
    event_date = pd.Timestamp(shock_results[0]["event_date"])
    ax.axvline(event_date, color="#E74C3C", linewidth=1.5, linestyle="--", zorder=5)
    ax.annotate(
        event_name,
        xy=(event_date, ax.get_ylim()[1]),
        xytext=(6, -12), textcoords="offset points",
        fontsize=9, color="#E74C3C",
    )

    ax.set_ylabel(f"{metric.replace('_', ' ').title()} Index", fontsize=11)
    ax.legend(fontsize=9)
    ax.set_title(
        f"Shock Resilience: {event_name}",
        fontsize=14, fontweight="bold", pad=15,
    )
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    fig.autofmt_xdate()
    _add_source(ax)
    fig.tight_layout()
    safe_save(fig, save_path)
    return fig


def plot_city_report(
    series,
    save_dir: str,
    events: Optional[list[dict]] = None,
) -> dict[str, plt.Figure]:
    """Generate ALL charts for a city and save them to save_dir.

    Args:
        series: RadianceSeries instance.
        save_dir: Directory path to save chart files.
        events: Optional list of event annotation dicts.

    Returns:
        Dict mapping chart name → Figure.
    """
    d = Path(save_dir)
    d.mkdir(parents=True, exist_ok=True)
    slug = series.city.lower().replace(" ", "_")

    figs = {}
    figs["gdp_population"] = plot_gdp_population(
        series, events=events, save_path=str(d / f"{slug}_gdp_population.png")
    )
    figs["per_capita"] = plot_per_capita_gdp(
        series, events=events, save_path=str(d / f"{slug}_per_capita.png")
    )
    figs["ppp_adjusted"] = plot_ppp_adjusted(
        series, save_path=str(d / f"{slug}_ppp_adjusted.png")
    )
    figs["raw_radiance"] = plot_raw_radiance(
        series, save_path=str(d / f"{slug}_raw_radiance.png")
    )
    return figs


def plot_comparison_report(
    series_list: list,
    save_dir: str,
) -> dict[str, plt.Figure]:
    """Generate multi-city comparison charts and save to save_dir.

    Args:
        series_list: List of RadianceSeries instances.
        save_dir: Directory path for saved files.

    Returns:
        Dict mapping chart name → Figure.
    """
    d = Path(save_dir)
    d.mkdir(parents=True, exist_ok=True)
    names = "_".join(s.city.lower().replace(" ", "_") for s in series_list[:3])

    figs = {}
    figs["comparison_dashboard"] = plot_city_comparison(
        series_list,
        save_path=str(d / f"{names}_comparison_dashboard.png"),
    )
    return figs


def plot_india_heatmap(
    state_annual: dict[str, pd.DataFrame],
    metric: str = "gdp_per_capita",
    title: str = "India States: GDP Per-Capita Growth (VIIRS Nighttime Lights)",
    save_path: Optional[str] = None,
) -> plt.Figure:
    """Heatmap of annual per-capita GDP index across all Indian states.

    Args:
        state_annual: Dict mapping state_name → annual DataFrame with columns
            'year' and metric (annual mean across selected districts).
            The metric should be an index where base_year = 100.
        metric: Column name to plot (default 'gdp_per_capita').
        title: Chart title.
        save_path: Optional path to save the figure.

    Returns:
        matplotlib Figure.
    """
    _apply_style()

    # Build wide matrix: rows = states, cols = years
    all_years = sorted({yr for df in state_annual.values() for yr in df["year"]})
    states = sorted(state_annual.keys())

    matrix = np.full((len(states), len(all_years)), np.nan)
    for i, state in enumerate(states):
        df = state_annual[state]
        year_to_val = dict(zip(df["year"], df[metric]))
        for j, yr in enumerate(all_years):
            matrix[i, j] = year_to_val.get(yr, np.nan)

    # Sort states by 2026 value (or last available year) descending
    last_col = matrix[:, -1]
    sort_idx = np.argsort(last_col)[::-1]
    matrix = matrix[sort_idx]
    states_sorted = [states[i] for i in sort_idx]

    # Normalise each state to its 2014 (first year) = 100 for fair comparison
    base_col = matrix[:, 0:1]
    base_col = np.where(base_col == 0, np.nan, base_col)
    matrix_norm = matrix / base_col * 100

    fig_h = max(10, len(states_sorted) * 0.45)
    fig, ax = plt.subplots(figsize=(16, fig_h))

    # Use a perceptually uniform diverging colormap centred at 100
    vmin = max(50, float(np.nanpercentile(matrix_norm, 5)))
    vmax = min(600, float(np.nanpercentile(matrix_norm, 95)))
    cmap = plt.get_cmap("RdYlGn")

    im = ax.imshow(
        matrix_norm,
        aspect="auto",
        cmap=cmap,
        vmin=vmin,
        vmax=vmax,
        interpolation="nearest",
    )

    # Axes labels
    ax.set_xticks(range(len(all_years)))
    ax.set_xticklabels([str(y) for y in all_years], fontsize=9, rotation=45, ha="right")
    ax.set_yticks(range(len(states_sorted)))
    ax.set_yticklabels(states_sorted, fontsize=9)

    # Annotate cells with the index value
    for i in range(len(states_sorted)):
        for j in range(len(all_years)):
            val = matrix_norm[i, j]
            if not np.isnan(val):
                txt_color = "white" if (val < vmin + (vmax - vmin) * 0.25 or
                                        val > vmin + (vmax - vmin) * 0.75) else "black"
                ax.text(j, i, f"{val:.0f}", ha="center", va="center",
                        fontsize=7, color=txt_color, fontweight="bold")

    cbar = fig.colorbar(im, ax=ax, shrink=0.6, pad=0.02)
    cbar.set_label("Per-Capita GDP Index (2014 = 100)", fontsize=10)

    ax.set_title(title, fontsize=14, fontweight="bold", pad=15)
    ax.set_xlabel("Year", fontsize=11)
    _add_source(ax)

    fig.tight_layout()
    safe_save(fig, save_path, dpi=150)
    return fig


def plot_india_bar_ranking(
    state_metrics: dict[str, float],
    title: str = "India States: Per-Capita GDP Growth 2014–2026",
    save_path: Optional[str] = None,
) -> plt.Figure:
    """Horizontal bar chart ranking all Indian states by a single metric.

    Args:
        state_metrics: Dict mapping state_name → metric value (e.g. % growth).
        title: Chart title.
        save_path: Optional save path.

    Returns:
        matplotlib Figure.
    """
    _apply_style()

    items = sorted(state_metrics.items(), key=lambda x: x[1])
    states = [i[0] for i in items]
    values = [i[1] for i in items]
    median_val = float(np.nanmedian(values))

    colors = [
        PALETTE[3] if v > median_val * 1.15 else
        PALETTE[1] if v < median_val * 0.85 else
        PALETTE[2]
        for v in values
    ]

    fig_h = max(8, len(states) * 0.38)
    fig, ax = plt.subplots(figsize=(14, fig_h))
    bars = ax.barh(states, values, color=colors, height=0.7)
    ax.axvline(median_val, color=SPINE_COLOR, linewidth=1.2, linestyle="--",
               label=f"Median ({median_val:.1f}%)")

    for bar, val in zip(bars, values):
        ax.text(bar.get_width() + 2, bar.get_y() + bar.get_height() / 2,
                f"{val:+.0f}%", va="center", fontsize=8, color=ANNOTATION_COLOR)

    green_patch = mpatches.Patch(color=PALETTE[3], label="Above median")
    amber_patch = mpatches.Patch(color=PALETTE[2], label="Near median")
    red_patch   = mpatches.Patch(color=PALETTE[1], label="Below median")
    ax.legend(handles=[green_patch, amber_patch, red_patch], fontsize=9, loc="lower right")

    ax.set_xlabel("Per-Capita GDP Growth % (2014 → 2026)", fontsize=11)
    ax.set_title(title, fontsize=14, fontweight="bold", pad=15)
    _add_source(ax)
    fig.tight_layout()
    safe_save(fig, save_path, dpi=150)
    return fig
