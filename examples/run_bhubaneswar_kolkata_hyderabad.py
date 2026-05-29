"""
Analysis: Bhubaneswar, Kolkata, Hyderabad (2014–2026)

Uses realistic synthetic VIIRS radiance data calibrated to each city's
known economic trajectory. The full pipeline runs identically to a live
GEE extraction — cloud correction, LTA (LED), GDP proxy, per-capita, PPP.

Synthetic data parameters:
  Hyderabad  — strong IT-driven growth, high LED adoption (Telangana SLNP)
  Kolkata    — moderate growth, mature city, slower LED transition
  Bhubaneswar — smart city programme, accelerating post-2016

Run:
    python examples/run_bhubaneswar_kolkata_hyderabad.py
"""

import matplotlib
matplotlib.use("Agg")

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np
import pandas as pd
from pathlib import Path

from nightlights_econ.cloud_correction import correct_cloud_bias, correction_stats
from nightlights_econ.gdp_proxy import compute_all_metrics
from nightlights_econ.lighting_tech import LightingTechConfig, apply_lighting_tech_adjustment, lta_correction_summary
from nightlights_econ.core import RadianceSeries
from nightlights_econ.analysis import (
    total_growth_pct, shock_analysis, growth_decomposition, compare_cities
)
from nightlights_econ.plotting import (
    plot_city_report, plot_comparison_report, plot_city_comparison, plot_rankings
)
from nightlights_econ.rankings import rank_cities
from nightlights_econ.utils import interpolate_population


OUTPUT_DIR = Path("./reports/bhubaneswar_kolkata_hyderabad")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────────────────────────────────────────
# City profiles (calibrated to known economic narratives)
# ─────────────────────────────────────────────────────────────────────────────

CITY_PROFILES = {
    "Hyderabad": {
        # IT hub (HITEC City), strong sustained growth 2014–2026
        "state": "telangana",
        "country_code": "IND",
        "base_radiance": 8.5,        # nW/cm²/sr — large, bright metro
        "total_growth_factor": 3.2,  # radiance nearly triples 2014→2026
        "growth_shape": "accelerating",
        "population_series": {
            2001: 5_740_000,
            2011: 7_750_000,
            2016: 9_200_000,
            2021: 10_500_000,
            2026: 11_800_000,
        },
        "area_km2": 650.0,
        "events": [
            {"date": "2014-06-01", "label": "Telangana Statehood"},
            {"date": "2020-12-01", "label": "HMDA expansion"},
        ],
    },
    "Kolkata": {
        # Mature metro, moderate growth, port economy
        "state": "west bengal",
        "country_code": "IND",
        "base_radiance": 7.2,
        "total_growth_factor": 1.9,  # ~90% growth over 12 years
        "growth_shape": "steady",
        "population_series": {
            2001: 4_572_876,
            2011: 4_496_694,
            2016: 4_800_000,
            2021: 5_100_000,
            2026: 5_400_000,
        },
        "area_km2": 205.0,
        "events": [
            {"date": "2021-05-01", "label": "Cyclone Yaas"},
        ],
    },
    "Bhubaneswar": {
        # Smart City programme, Odisha's capital — fast growth post-2016
        "state": "odisha",
        "country_code": "IND",
        "base_radiance": 3.8,        # smaller city, dimmer baseline
        "total_growth_factor": 2.8,
        "growth_shape": "smart_city_inflection",  # inflects upward post-2016
        "population_series": {
            2001: 647_302,
            2011: 837_737,
            2016: 960_000,
            2021: 1_100_000,
            2026: 1_280_000,
        },
        "area_km2": 135.0,
        "events": [
            {"date": "2016-01-01", "label": "Smart City selection"},
            {"date": "2023-03-01", "label": "Hockey World Cup"},
        ],
    },
}

# LED penetration for states not in the main dict
EXTRA_LED_PENETRATION = {
    "telangana": {
        2015: 0.03, 2016: 0.12, 2017: 0.28, 2018: 0.50, 2019: 0.67,
        2020: 0.79, 2021: 0.86, 2022: 0.91, 2023: 0.94, 2024: 0.96, 2025: 0.97,
    },
    "west bengal": {
        2015: 0.01, 2016: 0.04, 2017: 0.10, 2018: 0.24, 2019: 0.42,
        2020: 0.57, 2021: 0.68, 2022: 0.76, 2023: 0.83, 2024: 0.88, 2025: 0.91,
    },
    "odisha": {
        2015: 0.01, 2016: 0.03, 2017: 0.09, 2018: 0.22, 2019: 0.40,
        2020: 0.56, 2021: 0.68, 2022: 0.77, 2023: 0.84, 2024: 0.89, 2025: 0.92,
    },
}


def _generate_radiance(city_name: str, profile: dict, seed: int = 42) -> pd.DataFrame:
    """Generate realistic synthetic monthly VIIRS radiance for a city."""
    dates = pd.date_range("2014-01-01", "2026-03-01", freq="MS")
    n = len(dates)
    rng = np.random.default_rng(seed)

    base = profile["base_radiance"]
    g = profile["total_growth_factor"]
    shape = profile["growth_shape"]

    # Growth trajectory
    t = np.linspace(0, 1, n)
    if shape == "accelerating":
        trend = base * (1 + (g - 1) * t ** 1.4)
    elif shape == "steady":
        trend = base * (1 + (g - 1) * t)
    elif shape == "smart_city_inflection":
        # Slow growth until mid-2016 (~30 months in), then accelerates
        inflection = 30
        pre = np.linspace(0, 0.2, inflection)
        post = np.linspace(0.2, g - 1, n - inflection)
        growth_frac = np.concatenate([pre, post])
        trend = base * (1 + growth_frac)
    else:
        trend = base * (1 + (g - 1) * t)

    # Seasonal cycle (stronger in Bhubaneswar — coastal Odisha festivals)
    amp = 0.4 if city_name == "Bhubaneswar" else 0.3
    seasonal = amp * np.sin(2 * np.pi * np.arange(n) / 12 - np.pi / 2)

    # Noise
    noise = rng.normal(0, 0.25, n)

    radiance = trend + seasonal + noise
    radiance = np.maximum(radiance, 0.1)  # floor at 0.1

    # Cloud-free observations: low in monsoon (Jun-Sep)
    months = pd.DatetimeIndex(dates).month
    is_monsoon = np.isin(months, [6, 7, 8, 9])

    cf_clear = rng.integers(8, 15, n).astype(float)
    cf_cloudy = rng.integers(1, 5, n).astype(float)
    cf_obs = np.where(is_monsoon, cf_cloudy, cf_clear)

    # Monsoon bias: cloud cover dims the composite
    radiance[is_monsoon] *= rng.uniform(0.72, 0.88, is_monsoon.sum())

    # Cyclone / special events — inject shocks
    if city_name == "Kolkata":
        # Cyclone Yaas (May 2021): short dip
        cyclone_mask = (pd.DatetimeIndex(dates).year == 2021) & (pd.DatetimeIndex(dates).month.isin([5, 6]))
        radiance[cyclone_mask] *= 0.78

    return pd.DataFrame({
        "date": dates,
        "year": dates.year,
        "month": months,
        "radiance_raw": radiance,
        "cf_obs": cf_obs,
    })


# ─────────────────────────────────────────────────────────────────────────────
# PPP factors for India (embedded fallback)
# ─────────────────────────────────────────────────────────────────────────────
PPP_INDIA = {
    2014: 18.17, 2015: 18.69, 2016: 19.12, 2017: 19.58, 2018: 20.22,
    2019: 21.01, 2020: 21.87, 2021: 22.40, 2022: 23.19, 2023: 24.02,
    2024: 24.85, 2025: 25.70, 2026: 26.55,
}


# ─────────────────────────────────────────────────────────────────────────────
# Run full pipeline for each city
# ─────────────────────────────────────────────────────────────────────────────
all_series = {}

for city_name, profile in CITY_PROFILES.items():
    print(f"\n{'='*60}")
    print(f"  Analyzing {city_name}")
    print(f"{'='*60}")

    seed = {"Hyderabad": 7, "Kolkata": 13, "Bhubaneswar": 21}[city_name]
    df = _generate_radiance(city_name, profile, seed=seed)

    # Step 1 — Cloud correction
    df = correct_cloud_bias(df)
    stats = correction_stats(df)
    print(f"  Cloud correction: {stats['n_corrected']} monsoon months corrected "
          f"(mean uplift {stats['mean_uplift_pct']:.1f}%)")

    # Step 2 — Lighting Technology Adjustment
    lta = LightingTechConfig(
        country_code="IND",
        apply_led_correction=True,
        apply_electrification_correction=False,
        apply_efficiency_dampening=True,
        custom_led_penetration=EXTRA_LED_PENETRATION[profile["state"]],
    )
    df = apply_lighting_tech_adjustment(df, lta)
    lta_summary = lta_correction_summary(df)
    max_uplift_yr = lta_summary.loc[lta_summary["uplift_pct"].idxmax()]
    print(f"  LTA: peak LED correction in {int(max_uplift_yr['year'])} "
          f"(+{max_uplift_yr['uplift_pct']:.1f}% uplift)")

    # Step 3 — Population + PPP
    target_years = list(range(2014, 2027))
    pop = interpolate_population(profile["population_series"], target_years)
    ppp = interpolate_population(PPP_INDIA, target_years)

    # Step 4 — GDP metrics (use LTA-corrected radiance)
    df = compute_all_metrics(
        df, base_year=2014,
        population_by_year=pop,
        ppp_factors=ppp,
        radiance_col="radiance_lta",
        elasticity=0.95,
    )

    series = RadianceSeries(
        city=city_name,
        df=df,
        geometry_area_km2=profile["area_km2"],
        population_by_year=pop,
        ppp_factors=ppp,
        metadata={
            "base_year": 2014, "start_year": 2014, "end_year": 2026,
            "elasticity": 0.95, "lta_applied": True,
            "state": profile["state"],
        },
    )
    all_series[city_name] = series

    # Print summary
    gdp_g = total_growth_pct(series, "gdp_proxy")
    pc_g  = total_growth_pct(series, "gdp_per_capita")
    ppp_g = total_growth_pct(series, "gdp_ppp_per_capita")

    print(f"\n  ┌─────────────────────────────────────────┐")
    print(f"  │ {city_name:^41}│")
    print(f"  ├─────────────────────────────────────────┤")
    print(f"  │ GDP proxy growth (2014→2026): {gdp_g:+7.1f}%  │")
    print(f"  │ Per-capita GDP growth:        {pc_g:+7.1f}%  │")
    print(f"  │ PPP-adj per-capita growth:    {ppp_g:+7.1f}%  │")
    print(f"  │ Area: {profile['area_km2']:.0f} km²", " " * (26 - len(f"{profile['area_km2']:.0f}")), "│")
    pop_2026 = pop[2026] / 1e6
    print(f"  │ Population (2026 est): {pop_2026:.2f}M          │")
    print(f"  └─────────────────────────────────────────┘")

    # Generate per-city charts
    city_dir = OUTPUT_DIR / city_name.lower().replace(" ", "_")
    plot_city_report(series, save_dir=str(city_dir), events=profile["events"])
    print(f"  Charts → {city_dir}/")


# ─────────────────────────────────────────────────────────────────────────────
# Comparison and rankings
# ─────────────────────────────────────────────────────────────────────────────
series_list = list(all_series.values())

print(f"\n{'='*60}")
print("  COMPARATIVE RANKINGS")
print(f"{'='*60}")

ranking_pc = rank_cities(series_list, metric="per_capita_growth", top_n=3, bottom_n=1)
ranking_total = rank_cities(series_list, metric="total_growth", top_n=3, bottom_n=1)

print("\n  Per-Capita Growth (2014→2026):")
for _, row in ranking_pc.iterrows():
    print(f"    #{int(row['rank'])}  {row['city']:15s}  {row['per_capita_growth']:+.1f}%")

print("\n  Total GDP Proxy Growth:")
for _, row in ranking_total.iterrows():
    print(f"    #{int(row['rank'])}  {row['city']:15s}  {row['total_growth']:+.1f}%")


# ─────────────────────────────────────────────────────────────────────────────
# Shock analyses
# ─────────────────────────────────────────────────────────────────────────────
print(f"\n{'='*60}")
print("  SHOCK ANALYSES")
print(f"{'='*60}")

shocks = {
    "Bhubaneswar": {"date": "2016-01-01", "label": "Smart City programme (post-selection growth)"},
    "Kolkata":     {"date": "2021-05-01", "label": "Cyclone Yaas (May 2021)"},
    "Hyderabad":   {"date": "2014-06-01", "label": "Telangana statehood boost"},
}

shock_results = []
for city_name, evt in shocks.items():
    s = all_series[city_name]
    result = shock_analysis(s, event_date=evt["date"], window_months=18)
    if "error" not in result:
        result["city"] = city_name
        shock_results.append(result)
        direction = "growth" if result["drop_pct"] > 0 else "decline"
        print(f"\n  {city_name} — {evt['label']}")
        print(f"    Post-event change: {result['drop_pct']:+.1f}%  ({direction})")
        print(f"    Resilience score:  {result['resilience_score']:.0f}/100")


# ─────────────────────────────────────────────────────────────────────────────
# Generate comparison and rankings charts
# ─────────────────────────────────────────────────────────────────────────────
from nightlights_econ.plotting import plot_shock_resilience

print(f"\n{'='*60}")
print("  GENERATING COMPARISON CHARTS")
print(f"{'='*60}")

# Comparison dashboard
fig_dash = plot_city_comparison(
    series_list,
    save_path=str(OUTPUT_DIR / "comparison_dashboard.png"),
)
print(f"  Comparison dashboard → {OUTPUT_DIR}/comparison_dashboard.png")

# Rankings
fig_rank_pc = plot_rankings(
    ranking_pc,
    metric="per_capita_growth",
    title="Bhubaneswar · Kolkata · Hyderabad: Per-Capita GDP Growth (2014–2026)",
    save_path=str(OUTPUT_DIR / "rankings_per_capita.png"),
)
fig_rank_total = plot_rankings(
    ranking_total,
    metric="total_growth",
    title="Bhubaneswar · Kolkata · Hyderabad: Total GDP Proxy Growth (2014–2026)",
    save_path=str(OUTPUT_DIR / "rankings_total.png"),
)
print(f"  Rankings charts → {OUTPUT_DIR}/rankings_*.png")

# Shock resilience
if shock_results:
    fig_shock = plot_shock_resilience(
        shock_results,
        event_name="Selected city shocks",
        save_path=str(OUTPUT_DIR / "shock_resilience.png"),
    )
    print(f"  Shock resilience → {OUTPUT_DIR}/shock_resilience.png")

print(f"\n{'='*60}")
print(f"  All done. Charts in: {OUTPUT_DIR.resolve()}/")
print(f"{'='*60}")
