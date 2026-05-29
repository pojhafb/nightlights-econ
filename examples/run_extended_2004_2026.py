"""
Extended analysis: 2004–2026 using DMSP-OLS (2004-2013) + VIIRS (2014-2026).

For a set of cities, builds a unified 22-year nighttime lights time series:
  - 2004-2013: DMSP-OLS stable_lights, cross-calibrated to VIIRS units
               at the 2013 overlap year (annual only, ~2.7 km resolution)
  - 2014-2026: VIIRS VCMSLCFG monthly composites, cloud-corrected + LTA

Limitations of the DMSP era vs VIIRS era:
  - Annual granularity (no monthly seasonality)
  - ~2.7 km resolution (misses intra-district variation)
  - stable_lights band saturates at DN=63 over bright city cores
  - No monsoon correction (annual composites already integrate over cloud)
  - ~15-30% calibration uncertainty at the splice

Cities analysed: the 22 cities already in the cache + a few additions.
"""

import matplotlib; matplotlib.use("Agg")
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import ee
import numpy as np
import pandas as pd
from pathlib import Path

from nightlights_econ.cache import geometry_key, get_cached
from nightlights_econ.extractor import extract_for_district
from nightlights_econ.dmsp import (
    extract_dmsp_annual, compute_viirs_annual_mean,
    cross_calibrate_dmsp_to_viirs, build_unified_series,
)
from nightlights_econ.cloud_correction import correct_cloud_bias
from nightlights_econ.lighting_tech import LightingTechConfig, apply_lighting_tech_adjustment
from nightlights_econ.gdp_proxy import compute_all_metrics
from nightlights_econ.core import RadianceSeries
from nightlights_econ.analysis import total_growth_pct
from nightlights_econ.india_census import district_population_series
from nightlights_econ.utils import interpolate_population
from nightlights_econ.plotting import plot_city_report, plot_city_comparison, plot_rankings
from nightlights_econ.rankings import rank_cities

PROJECT    = "nightlights-analysis"
VIIRS_START, VIIRS_END = 2014, 2026
DMSP_START,  DMSP_END  = 2004, 2013
BASE_YR    = 2004          # index 2004=100 for the extended series
ELASTICITY = 0.95
OUTPUT_DIR = Path("./reports/extended_2004_2026")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PPP_INDIA = {
    2004: 14.81, 2005: 15.13, 2006: 15.58, 2007: 16.12, 2008: 17.09,
    2009: 17.49, 2010: 17.88, 2011: 18.07, 2012: 18.44, 2013: 17.97,
    2014: 18.17, 2015: 18.69, 2016: 19.12, 2017: 19.58, 2018: 20.22,
    2019: 21.01, 2020: 21.87, 2021: 22.40, 2022: 23.19, 2023: 24.02,
    2024: 24.85, 2025: 25.70, 2026: 26.55,
}

DEFAULT_LED = {
    2004: 0.00, 2005: 0.00, 2006: 0.00, 2007: 0.00, 2008: 0.00,
    2009: 0.00, 2010: 0.00, 2011: 0.00, 2012: 0.00, 2013: 0.00,
    2014: 0.01, 2015: 0.04, 2016: 0.10, 2017: 0.22, 2018: 0.40,
    2019: 0.57, 2020: 0.70, 2021: 0.79, 2022: 0.86, 2023: 0.91,
    2024: 0.94, 2025: 0.96, 2026: 0.97,
}

# Cities: (display_name, admin2_GAUL, admin1_GAUL, state_for_census)
CITIES = [
    ("Hyderabad",       "Hyderabad",        "Andhra Pradesh",  "Andhra Pradesh"),
    ("Bengaluru",       "Bangalore Urban",  "Karnataka",       "Karnataka"),
    ("Chennai",         "Chennai",          "Tamil Nadu",      "Tamil Nadu"),
    ("Kolkata",         "Kolkata",          "West Bengal",     "West Bengal"),
    ("Pune",            "Pune",             "Maharashtra",     "Maharashtra"),
    ("Lucknow",         "Lucknow",          "Uttar Pradesh",   "Uttar Pradesh"),
    ("Varanasi",        "Varanasi",         "Uttar Pradesh",   "Uttar Pradesh"),
    ("Allahabad",       "Allahabad",        "Uttar Pradesh",   "Uttar Pradesh"),
    ("Jaipur",          "Jaipur",           "Rajasthan",       "Rajasthan"),
    ("Bhubaneswar",     "Khordha",          "Orissa",          "Orissa"),
    ("Coimbatore",      "Coimbatore",       "Tamil Nadu",      "Tamil Nadu"),
    ("Ahmedabad",       "Ahmadabad",        "Gujarat",         "Gujarat"),
    ("Nagpur",          "Nagpur",           "Maharashtra",     "Maharashtra"),
    ("Patna",           "Patna",            "Bihar",           "Bihar"),
    ("Guwahati",        "Kamrup",           "Assam",           "Assam"),
]

print("Initializing GEE…")
ee.Initialize(project=PROJECT)
gaul = ee.FeatureCollection("FAO/GAUL/2015/level2")
print("GEE OK\n")


def get_geometry(admin2, admin1):
    return (gaul
            .filter(ee.Filter.eq("ADM2_NAME", admin2))
            .filter(ee.Filter.eq("ADM1_NAME", admin1))
            .filter(ee.Filter.eq("ADM0_NAME", "India"))
            .first().geometry())


all_series = {}

for display, admin2, admin1, census_state in CITIES:
    print(f"\n{'='*65}")
    print(f"  {display}  ({admin2} / {admin1})")
    print(f"{'='*65}")

    geo_key = geometry_key(admin2, admin1, "India")
    geom    = get_geometry(admin2, admin1)

    # ── VIIRS 2014-2026 (from cache or GEE) ────────────────────────────────
    print("  [VIIRS 2014-2026]", end=" ")
    viirs_df = get_cached(geo_key, VIIRS_START, VIIRS_END, 500)
    if viirs_df is None:
        print("fetching from GEE…")
        viirs_df = extract_for_district(admin2, admin1, "India", VIIRS_START, VIIRS_END)
    else:
        print(f"cache hit ({len(viirs_df)} rows)")

    viirs_df = correct_cloud_bias(viirs_df)
    lta = LightingTechConfig(
        country_code="IND", apply_led_correction=True,
        apply_electrification_correction=False, apply_efficiency_dampening=True,
        custom_led_penetration=DEFAULT_LED,
    )
    viirs_df = apply_lighting_tech_adjustment(viirs_df, lta)

    # Annual average of the VIIRS series (to splice with DMSP annual)
    viirs_annual = (viirs_df.groupby("year")
                    .agg(radiance_corrected=("radiance_corrected", "mean"),
                         radiance_lta=("radiance_lta", "mean"))
                    .reset_index())
    viirs_annual["date"] = pd.to_datetime(viirs_annual["year"].astype(str) + "-07-01")
    viirs_annual["month"] = 7
    viirs_annual["cf_obs"] = float("nan")

    # ── DMSP 2004-2013 ──────────────────────────────────────────────────────
    print("  [DMSP 2004-2013]", end=" ")
    dmsp_df = extract_dmsp_annual(geom, geo_key, DMSP_START, DMSP_END)
    print(f"{len(dmsp_df)} annual observations")

    # Cross-calibrate: get VIIRS 2013 annual mean for this geometry
    print("  [Calibrating DMSP → VIIRS units at 2013]…", end=" ")
    # Try cache first (VIIRS 2013 mean from the VIIRS series we already have)
    viirs_2013_mean = float(viirs_annual[viirs_annual["year"] == 2013]["radiance_corrected"].iloc[0]) \
        if 2013 in viirs_annual["year"].values else float("nan")

    if np.isnan(viirs_2013_mean):
        # Fetch 2013 directly from VCMCFG
        viirs_2013_mean = compute_viirs_annual_mean(geom, 2013)

    dmsp_2013_dn = float(dmsp_df[dmsp_df["year"] == 2013]["radiance_raw"].iloc[0])
    scale_factor = viirs_2013_mean / dmsp_2013_dn if dmsp_2013_dn > 0 else 1.0
    print(f"scale={scale_factor:.3f}  (DMSP 2013 DN={dmsp_2013_dn:.2f} → VIIRS {viirs_2013_mean:.3f} nW/cm²/sr)")

    try:
        dmsp_cal = cross_calibrate_dmsp_to_viirs(dmsp_df, viirs_2013_mean, dmsp_2013_dn)
    except ValueError as e:
        print(f"  WARNING: calibration failed ({e}), skipping DMSP era for {display}")
        continue

    # ── Splice into unified 2004-2026 annual series ─────────────────────────
    unified = build_unified_series(dmsp_cal, viirs_annual)
    unified["radiance_raw"] = unified.get("radiance_raw", unified["radiance_corrected"])

    # ── GDP metrics ──────────────────────────────────────────────────────────
    target_years = list(range(DMSP_START, VIIRS_END + 1))
    pop = district_population_series(census_state, admin2, target_years)
    ppp = interpolate_population(PPP_INDIA, target_years)

    # Need year/month cols for compute_all_metrics
    unified["year"]  = unified["year"].astype(int)
    unified["month"] = 7

    try:
        unified = compute_all_metrics(
            unified, base_year=BASE_YR,
            population_by_year=pop,
            ppp_factors=ppp,
            radiance_col="radiance_lta",
            elasticity=ELASTICITY,
        )
    except Exception as e:
        print(f"  WARNING: GDP metrics failed for {display}: {e}")
        continue

    series = RadianceSeries(
        city=display,
        df=unified,
        geometry_area_km2=0.0,
        population_by_year=pop,
        ppp_factors=ppp,
        metadata={
            "base_year": BASE_YR, "start_year": DMSP_START, "end_year": VIIRS_END,
            "elasticity": ELASTICITY, "lta_applied": True,
            "source": "DMSP+VIIRS unified", "dmsp_scale_factor": scale_factor,
        },
    )
    all_series[display] = series

    # Print summary
    g_proxy  = total_growth_pct(series, "gdp_proxy")
    g_pc     = total_growth_pct(series, "gdp_per_capita")
    g_ppp    = total_growth_pct(series, "gdp_ppp_per_capita")

    # Period breakdowns
    def period_growth(col, y1, y2):
        sub = unified[unified["year"].isin([y1, y2])].groupby("year")[col].mean()
        if y1 in sub.index and y2 in sub.index and sub[y1] > 0:
            return (sub[y2] - sub[y1]) / sub[y1] * 100
        return float("nan")

    g_04_09 = period_growth("gdp_per_capita", 2004, 2009)
    g_09_14 = period_growth("gdp_per_capita", 2009, 2014)
    g_14_19 = period_growth("gdp_per_capita", 2014, 2019)
    g_19_26 = period_growth("gdp_per_capita", 2019, 2026)

    print(f"\n  ┌{'─'*51}┐")
    print(f"  │ {display:^51}│")
    print(f"  ├{'─'*51}┤")
    print(f"  │ Full period (2004→2026):                          │")
    print(f"  │   GDP proxy growth:          {g_proxy:>+8.1f}%           │")
    print(f"  │   Per-capita growth:         {g_pc:>+8.1f}%           │")
    print(f"  │   PPP-adj per-capita:        {g_ppp:>+8.1f}%           │")
    print(f"  ├{'─'*51}┤")
    print(f"  │ Period breakdown (per-capita GDP):                │")
    print(f"  │   2004→2009 (UPA-2 boom):    {g_04_09:>+8.1f}%           │")
    print(f"  │   2009→2014 (slowdown):      {g_09_14:>+8.1f}%           │")
    print(f"  │   2014→2019 (NDA-1):         {g_14_19:>+8.1f}%           │")
    print(f"  │   2019→2026 (post-Covid):    {g_19_26:>+8.1f}%           │")
    print(f"  └{'─'*51}┘")

    # Save charts (use annual df)
    city_dir = OUTPUT_DIR / display.lower().replace(" ", "_")
    plot_city_report(series, save_dir=str(city_dir))
    print(f"  Charts → {city_dir}/")


# ── Rankings ────────────────────────────────────────────────────────────────
series_list = list(all_series.values())

print(f"\n{'='*65}")
print("  FULL-PERIOD RANKINGS: Per-Capita Growth 2004→2026")
print(f"{'='*65}")
ranking = rank_cities(series_list, metric="per_capita_growth", top_n=len(series_list), bottom_n=0)
for _, r in ranking.iterrows():
    print(f"    #{int(r['rank']):>2}  {r['city']:20s}  {r['per_capita_growth']:>+.1f}%")

plot_city_comparison(
    series_list[:8],
    metric="gdp_per_capita",
    save_path=str(OUTPUT_DIR / "extended_comparison_dashboard.png"),
)
plot_rankings(
    ranking, metric="per_capita_growth",
    title="India Cities: Per-Capita GDP Growth 2004–2026 (DMSP + VIIRS)",
    save_path=str(OUTPUT_DIR / "extended_rankings.png"),
)

# Export unified CSV
rows = []
for name, s in all_series.items():
    for _, row in s.df.iterrows():
        rows.append({
            "city": name, "year": int(row["year"]),
            "source": row.get("source", "VIIRS"),
            "radiance_lta": round(row.get("radiance_lta", float("nan")), 4),
            "gdp_proxy": round(row.get("gdp_proxy", float("nan")), 2),
            "gdp_per_capita": round(row.get("gdp_per_capita", float("nan")), 2),
            "gdp_ppp_per_capita": round(row.get("gdp_ppp_per_capita", float("nan")), 2),
        })
csv_path = OUTPUT_DIR / "extended_2004_2026.csv"
pd.DataFrame(rows).to_csv(csv_path, index=False)
print(f"\n  CSV → {csv_path}")
print(f"\n{'='*65}")
print(f"  Done. All outputs in: {OUTPUT_DIR.resolve()}/")
print(f"{'='*65}")
