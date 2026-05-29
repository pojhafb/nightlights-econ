"""
India-wide analysis: all states, population-ratio-selected districts, heatmap.

For each of India's 34 GAUL states/UTs:
  - Select districts where district_pop / state_pop >= THRESHOLD (default 5%)
    with a minimum of 2 and maximum of 8 per state.
  - Fetch VIIRS 2014–2026 via cache (0 GEE calls if already cached, else 1 per district).
  - Run cloud correction + LTA + GDP proxy pipeline.
  - Aggregate to state-level annual average per-capita index.

Output:
  - India heatmap (states × years, colour = per-capita GDP index)
  - India bar ranking (all states sorted by 2014→2026 per-capita growth)
  - Per-state city charts
  - CSV of all state-level results
"""

import matplotlib; matplotlib.use("Agg")
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import ee
import numpy as np
import pandas as pd
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from nightlights_econ.cache import geometry_key, get_cached, cache_info
from nightlights_econ.extractor import extract_for_district
from nightlights_econ.cloud_correction import correct_cloud_bias
from nightlights_econ.gdp_proxy import compute_all_metrics
from nightlights_econ.lighting_tech import LightingTechConfig, apply_lighting_tech_adjustment
from nightlights_econ.core import RadianceSeries
from nightlights_econ.analysis import total_growth_pct
from nightlights_econ.plotting import (
    plot_india_heatmap, plot_india_bar_ranking, plot_rankings, plot_city_comparison
)
from nightlights_econ.rankings import rank_cities
from nightlights_econ.india_census import DISTRICT_POP, select_districts, state_population, all_states
from nightlights_econ.utils import interpolate_population

PROJECT    = "nightlights-analysis"
START_YR   = 2014
END_YR     = 2026
BASE_YR    = 2014
SCALE      = 500
CF_THRESH  = 8
ELASTICITY = 0.95
THRESHOLD  = 0.05    # district must be >= 5% of state population
MAX_WORKERS = 6      # parallel GEE fetches
OUTPUT_DIR = Path("./reports/india_all_states")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PPP_INDIA = {
    2014: 18.17, 2015: 18.69, 2016: 19.12, 2017: 19.58, 2018: 20.22,
    2019: 21.01, 2020: 21.87, 2021: 22.40, 2022: 23.19, 2023: 24.02,
    2024: 24.85, 2025: 25.70, 2026: 26.55,
}

# Default India LED curve (state-specific via LightingTechConfig.state if needed)
DEFAULT_LED = {
    2014: 0.01, 2015: 0.04, 2016: 0.10, 2017: 0.22, 2018: 0.40,
    2019: 0.57, 2020: 0.70, 2021: 0.79, 2022: 0.86, 2023: 0.91,
    2024: 0.94, 2025: 0.96, 2026: 0.97,
}

print("Initializing GEE…")
ee.Initialize(project=PROJECT)
print("GEE OK\n")

# ─────────────────────────────────────────────────────────────────────────────
# Build district list across all states
# ─────────────────────────────────────────────────────────────────────────────
print(f"Building district list (threshold={THRESHOLD*100:.0f}% of state pop)…\n")

all_districts = []   # (state, district, ratio)
for state in all_states():
    selected = select_districts(state, threshold=THRESHOLD)
    for dist, ratio in selected:
        all_districts.append((state, dist, ratio))

print(f"  {len(all_districts)} districts selected across {len(all_states())} states\n")

# Print selection summary
print(f"  {'State':30s}  {'Districts selected':>4}")
print(f"  {'─'*30}  {'─'*4}")
for state in all_states():
    sel = select_districts(state, threshold=THRESHOLD)
    print(f"  {state:30s}  {len(sel):>4}  ({', '.join(d for d,_ in sel[:4])}{'…' if len(sel)>4 else ''})")

# ─────────────────────────────────────────────────────────────────────────────
# Fetch / cache all districts (parallelised)
# ─────────────────────────────────────────────────────────────────────────────
print(f"\nFetching VIIRS data ({MAX_WORKERS} parallel workers)…")
print("  Cache hits cost 0 GEE calls. Misses use 1 call each (batch extractor).\n")

_print_lock = threading.Lock()

def fetch_one(args):
    state, district, ratio = args
    key = geometry_key(district, state, "India")
    cached = get_cached(key, START_YR, END_YR, SCALE)
    if cached is not None:
        with _print_lock:
            print(f"  ✓ {state:25s} / {district:25s} — cached")
        return state, district, ratio, cached
    with _print_lock:
        print(f"  ↓ {state:25s} / {district:25s} — fetching…")
    try:
        df = extract_for_district(district, state, "India", START_YR, END_YR, SCALE)
        with _print_lock:
            print(f"    → {len(df)} rows stored for {district}/{state}")
        return state, district, ratio, df
    except Exception as exc:
        with _print_lock:
            print(f"  ✗ {state:25s} / {district:25s} — FAILED: {exc}")
        return state, district, ratio, None

raw_data: dict[tuple, pd.DataFrame] = {}
with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
    futures = {pool.submit(fetch_one, args): args for args in all_districts}
    for future in as_completed(futures):
        state, district, ratio, df = future.result()
        if df is not None:
            raw_data[(state, district)] = df

print(f"\n  {len(raw_data)}/{len(all_districts)} districts successfully retrieved.\n")

# ─────────────────────────────────────────────────────────────────────────────
# Run pipeline for each district
# ─────────────────────────────────────────────────────────────────────────────
print("Running pipeline (cloud correction → LTA → GDP metrics)…")

all_series: dict[str, list[RadianceSeries]] = {}   # state → list of RadianceSeries

target_years = list(range(START_YR, END_YR + 1))
ppp = interpolate_population(PPP_INDIA, target_years)

for (state, district), raw_df in raw_data.items():
    try:
        df = correct_cloud_bias(raw_df.copy(), cf_threshold=CF_THRESH)

        lta = LightingTechConfig(
            country_code="IND",
            state=state.lower(),
            apply_led_correction=True,
            apply_electrification_correction=False,
            apply_efficiency_dampening=True,
            custom_led_penetration=DEFAULT_LED,
        )
        df = apply_lighting_tech_adjustment(df, lta)

        dist_pop = DISTRICT_POP.get(state, {}).get(district, 500_000)
        pop = {yr: dist_pop * (1.015 ** (yr - 2011)) for yr in target_years}

        df = compute_all_metrics(
            df, base_year=BASE_YR,
            population_by_year=pop,
            ppp_factors=ppp,
            radiance_col="radiance_lta",
            elasticity=ELASTICITY,
        )

        series = RadianceSeries(
            city=f"{district} ({state})",
            df=df,
            geometry_area_km2=0.0,
            population_by_year=pop,
            ppp_factors=ppp,
            metadata={"base_year": BASE_YR, "state": state, "district": district,
                      "lta_applied": True, "source": "VIIRS/GEE"},
        )
        all_series.setdefault(state, []).append(series)

    except Exception as exc:
        print(f"  Pipeline failed for {district}/{state}: {exc}")

print(f"  Pipeline complete for {sum(len(v) for v in all_series.values())} districts.\n")

# ─────────────────────────────────────────────────────────────────────────────
# Aggregate to state level
# ─────────────────────────────────────────────────────────────────────────────
print("Aggregating to state level…")

state_annual: dict[str, pd.DataFrame] = {}
state_growth: dict[str, float] = {}

for state, series_list in all_series.items():
    # Annual mean per-capita GDP index across all selected districts
    frames = []
    for s in series_list:
        ann = s.annual_df[["year", "gdp_per_capita"]].copy()
        frames.append(ann)

    if not frames:
        continue

    combined = pd.concat(frames).groupby("year")["gdp_per_capita"].mean().reset_index()
    state_annual[state] = combined

    # Total per-capita growth: last year / first year
    first = combined["gdp_per_capita"].iloc[0]
    last  = combined["gdp_per_capita"].iloc[-1]
    state_growth[state] = (last - first) / first * 100 if first > 0 else float("nan")

# Print summary table
print(f"\n{'='*65}")
print(f"  {'State':30s}  {'Districts':>9}  {'Per-Cap Growth':>14}")
print(f"  {'─'*30}  {'─'*9}  {'─'*14}")
for state in sorted(state_growth, key=lambda s: state_growth[s], reverse=True):
    n = len(all_series.get(state, []))
    g = state_growth[state]
    print(f"  {state:30s}  {n:>9}  {g:>+13.1f}%")

# ─────────────────────────────────────────────────────────────────────────────
# Charts
# ─────────────────────────────────────────────────────────────────────────────
print(f"\nGenerating charts…")

# 1. Heatmap
fig_heat = plot_india_heatmap(
    state_annual,
    metric="gdp_per_capita",
    title="India States: Per-Capita GDP Growth (VIIRS Nighttime Lights + LED Correction)",
    save_path=str(OUTPUT_DIR / "india_heatmap.png"),
)
print(f"  Heatmap → {OUTPUT_DIR}/india_heatmap.png")

# 2. Bar ranking
fig_bar = plot_india_bar_ranking(
    state_growth,
    title="India States: Per-Capita GDP Growth 2014–2026 (VIIRS + LED correction)",
    save_path=str(OUTPUT_DIR / "india_bar_ranking.png"),
)
print(f"  Bar ranking → {OUTPUT_DIR}/india_bar_ranking.png")

# 3. CSV export
rows = []
for state, ann in state_annual.items():
    for _, row in ann.iterrows():
        rows.append({
            "state": state,
            "year": int(row["year"]),
            "gdp_per_capita_index": round(row["gdp_per_capita"], 2),
            "n_districts": len(all_series.get(state, [])),
        })
csv_path = OUTPUT_DIR / "india_state_annual.csv"
pd.DataFrame(rows).to_csv(csv_path, index=False)
print(f"  CSV → {csv_path}")

# 4. Cache summary
info = cache_info()
print(f"\n  Cache: {len(info)} total districts stored in SQLite")

print(f"\n{'='*65}")
print(f"  Done. All outputs in: {OUTPUT_DIR.resolve()}/")
print(f"{'='*65}")
