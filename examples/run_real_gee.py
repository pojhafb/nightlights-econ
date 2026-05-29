"""
Real GEE extraction: Bhubaneswar, Kolkata, Hyderabad, Greater Hyderabad (2014–2026).

Fetches actual VIIRS DNB monthly radiance via Google Earth Engine,
then runs the full pipeline: cloud correction → LTA → GDP proxy → charts.

Greater Hyderabad = Hyderabad district (old city) ∪ Rangareddi district
(contains HITEC City, Cyberabad, Gachibowli, Madhapur).
"""

import matplotlib
matplotlib.use("Agg")

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np
import pandas as pd
from pathlib import Path

import ee

from nightlights_econ.cloud_correction import correct_cloud_bias, correction_stats
from nightlights_econ.gdp_proxy import compute_all_metrics
from nightlights_econ.lighting_tech import LightingTechConfig, apply_lighting_tech_adjustment, lta_correction_summary
from nightlights_econ.core import RadianceSeries
from nightlights_econ.analysis import total_growth_pct, shock_analysis
from nightlights_econ.plotting import plot_city_report, plot_city_comparison, plot_rankings
from nightlights_econ.rankings import rank_cities
from nightlights_econ.utils import interpolate_population

PROJECT   = "nightlights-analysis"
START_YR  = 2014
END_YR    = 2026
BASE_YR   = 2014
SCALE     = 500          # metres — native VIIRS resolution
RAD_CAP   = 100.0        # nW/cm²/sr — excludes gas flares
CF_THRESH = 8
ELASTICITY = 0.95        # India-specific (Vaidya 2024)
OUTPUT_DIR = Path("./reports/real_gee")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

print("Initializing GEE…")
ee.Initialize(project=PROJECT)
print("GEE OK\n")

# ─────────────────────────────────────────────────────────────────────────────
# City definitions
# ─────────────────────────────────────────────────────────────────────────────
CITIES = {
    "Hyderabad": {
        "admin2": "Hyderabad",
        "admin1": "Andhra Pradesh",   # GAUL 2015 predates Telangana statehood
        "country": "India",
        "state_led": "telangana",
        "population": {2001: 5_740_000, 2011: 7_750_000, 2021: 10_500_000, 2026: 11_800_000},
        "events": [
            {"date": "2014-06-02", "label": "Telangana Statehood"},
        ],
    },
    "Kolkata": {
        "admin2": "Kolkata",
        "admin1": "West Bengal",
        "country": "India",
        "state_led": "west bengal",
        "population": {2001: 4_572_876, 2011: 4_496_694, 2021: 5_100_000, 2026: 5_400_000},
        "events": [
            {"date": "2021-05-26", "label": "Cyclone Yaas"},
        ],
    },
    "Bhubaneswar": {
        "admin2": "Khordha",   # Bhubaneswar is in Khordha district
        "admin1": "Orissa",    # GAUL 2015 uses old state name
        "country": "India",
        "state_led": "odisha",
        "population": {2001: 647_302, 2011: 837_737, 2021: 1_100_000, 2026: 1_280_000},
        "events": [
            {"date": "2016-01-28", "label": "Smart City selection"},
            {"date": "2023-01-13", "label": "Hockey World Cup"},
        ],
    },
}

# Greater Hyderabad = Hyderabad + Rangareddi districts (union geometry)
GREATER_HYDERABAD = {
    "districts": [
        ("Hyderabad",  "Andhra Pradesh", "India"),
        ("Rangareddi", "Andhra Pradesh", "India"),
    ],
    "state_led": "telangana",
    # Hyderabad district ~4M + Rangareddi ~5.3M → combined metro population
    "population": {2001: 7_700_000, 2011: 9_700_000, 2021: 14_500_000, 2026: 17_000_000},
    "events": [
        {"date": "2014-06-02", "label": "Telangana Statehood"},
        {"date": "2019-12-01", "label": "HMDA master plan"},
    ],
}

LED_PENETRATION = {
    "telangana": {
        2014: 0.01, 2015: 0.03, 2016: 0.12, 2017: 0.28, 2018: 0.50,
        2019: 0.67, 2020: 0.79, 2021: 0.86, 2022: 0.91, 2023: 0.94,
        2024: 0.96, 2025: 0.97, 2026: 0.97,
    },
    "west bengal": {
        2014: 0.00, 2015: 0.01, 2016: 0.04, 2017: 0.10, 2018: 0.24,
        2019: 0.42, 2020: 0.57, 2021: 0.68, 2022: 0.76, 2023: 0.83,
        2024: 0.88, 2025: 0.91, 2026: 0.92,
    },
    "odisha": {
        2014: 0.00, 2015: 0.01, 2016: 0.03, 2017: 0.09, 2018: 0.22,
        2019: 0.40, 2020: 0.56, 2021: 0.68, 2022: 0.77, 2023: 0.84,
        2024: 0.89, 2025: 0.92, 2026: 0.93,
    },
}

PPP_INDIA = {
    2014: 18.17, 2015: 18.69, 2016: 19.12, 2017: 19.58, 2018: 20.22,
    2019: 21.01, 2020: 21.87, 2021: 22.40, 2022: 23.19, 2023: 24.02,
    2024: 24.85, 2025: 25.70, 2026: 26.55,
}


# ─────────────────────────────────────────────────────────────────────────────
# GEE extraction helpers
# ─────────────────────────────────────────────────────────────────────────────

def resolve_geometry(admin2, admin1, country):
    gaul = ee.FeatureCollection("FAO/GAUL/2015/level2")
    feat = (gaul
            .filter(ee.Filter.eq("ADM2_NAME", admin2))
            .filter(ee.Filter.eq("ADM1_NAME", admin1))
            .filter(ee.Filter.eq("ADM0_NAME", country))
            .first())
    return feat.geometry()


def resolve_union_geometry(districts: list[tuple[str, str, str]]):
    """Merge multiple (admin2, admin1, country) districts into one geometry."""
    gaul = ee.FeatureCollection("FAO/GAUL/2015/level2")
    geoms = []
    for admin2, admin1, country in districts:
        feat = (gaul
                .filter(ee.Filter.eq("ADM2_NAME", admin2))
                .filter(ee.Filter.eq("ADM1_NAME", admin1))
                .filter(ee.Filter.eq("ADM0_NAME", country))
                .first())
        geoms.append(feat.geometry())
    combined = ee.Geometry.MultiPolygon(
        ee.List(geoms).map(lambda g: ee.Geometry(g).coordinates()).flatten()
    )
    return combined.dissolve(maxError=100)


def extract_viirs(geometry, start_yr, end_yr):
    """Pull monthly VIIRS mean radiance + CF obs for a geometry."""
    collection = (
        ee.ImageCollection("NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG")
        .filterDate(f"{start_yr}-01-01", f"{end_yr + 1}-01-01")
        .filterBounds(geometry)
    )

    records = []
    images = collection.toList(collection.size())
    n = collection.size().getInfo()
    print(f"    {n} monthly images found")

    for i in range(n):
        img = ee.Image(images.get(i))
        date_ms = img.get("system:time_start").getInfo()
        date = pd.Timestamp(date_ms, unit="ms")

        rad_img = img.select("avg_rad").min(ee.Image.constant(RAD_CAP))
        cf_img  = img.select("cf_cvg")

        result = (
            rad_img.rename("avg_rad")
                   .addBands(cf_img.rename("cf_cvg"))
                   .reduceRegion(
                       reducer=ee.Reducer.mean(),
                       geometry=geometry,
                       scale=SCALE,
                       maxPixels=1e9,
                   )
                   .getInfo()
        )

        rad_val = result.get("avg_rad", float("nan"))
        cf_val  = result.get("cf_cvg",  float("nan"))

        if rad_val is not None and rad_val != rad_val:
            rad_val = float("nan")

        records.append({
            "date":        date,
            "year":        date.year,
            "month":       date.month,
            "radiance_raw": float(rad_val) if rad_val is not None else float("nan"),
            "cf_obs":       float(cf_val)  if cf_val  is not None else float("nan"),
        })

        if (i + 1) % 12 == 0:
            print(f"      … {i+1}/{n} months fetched")

    return pd.DataFrame(records).sort_values("date").reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────────────────
# Main loop
# ─────────────────────────────────────────────────────────────────────────────
all_series = {}

for city_name, cfg in CITIES.items():
    print(f"\n{'='*60}")
    print(f"  {city_name}")
    print(f"{'='*60}")

    # 1. Geometry
    print("  Resolving boundary from GAUL…")
    geom = resolve_geometry(cfg["admin2"], cfg["admin1"], cfg["country"])
    area_km2 = geom.area(maxError=100).getInfo() / 1e6
    print(f"  Area: {area_km2:.0f} km²")

    # 2. Extract VIIRS
    print(f"  Fetching VIIRS {START_YR}–{END_YR}…")
    df = extract_viirs(geom, START_YR, END_YR)
    print(f"  Fetched {len(df)} monthly observations")
    print(f"  Radiance range: {df['radiance_raw'].min():.2f} – {df['radiance_raw'].max():.2f} nW/cm²/sr")

    # 3. Cloud correction
    df = correct_cloud_bias(df, cf_threshold=CF_THRESH)
    stats = correction_stats(df)
    print(f"  Cloud correction: {stats['n_corrected']} months corrected "
          f"(mean uplift {stats['mean_uplift_pct']:.1f}%, max {stats['max_uplift_pct']:.1f}%)")

    # 4. Lighting Technology Adjustment
    lta = LightingTechConfig(
        country_code="IND",
        apply_led_correction=True,
        apply_electrification_correction=False,
        apply_efficiency_dampening=True,
        custom_led_penetration=LED_PENETRATION[cfg["state_led"]],
    )
    df = apply_lighting_tech_adjustment(df, lta)
    lta_sum = lta_correction_summary(df)
    peak = lta_sum.loc[lta_sum["uplift_pct"].idxmax()]
    print(f"  LTA: peak correction {peak['uplift_pct']:.1f}% in {int(peak['year'])}")

    # 5. Population + PPP
    target_years = list(range(START_YR, END_YR + 1))
    pop  = interpolate_population(cfg["population"], target_years)
    ppp  = interpolate_population(PPP_INDIA, target_years)

    # 6. GDP metrics
    df = compute_all_metrics(
        df, base_year=BASE_YR,
        population_by_year=pop,
        ppp_factors=ppp,
        radiance_col="radiance_lta",
        elasticity=ELASTICITY,
    )

    series = RadianceSeries(
        city=city_name,
        df=df,
        geometry_area_km2=area_km2,
        population_by_year=pop,
        ppp_factors=ppp,
        metadata={
            "base_year": BASE_YR, "start_year": START_YR, "end_year": END_YR,
            "elasticity": ELASTICITY, "lta_applied": True,
            "state": cfg["state_led"], "source": "VIIRS/GEE (real)",
        },
    )
    all_series[city_name] = series

    # 7. Print results
    gdp_g = total_growth_pct(series, "gdp_proxy")
    pc_g  = total_growth_pct(series, "gdp_per_capita")
    ppp_g = total_growth_pct(series, "gdp_ppp_per_capita")
    pop26 = pop[2026] / 1e6

    print(f"\n  ┌─────────────────────────────────────────┐")
    print(f"  │ {city_name:^41}│")
    print(f"  ├─────────────────────────────────────────┤")
    print(f"  │ GDP proxy growth (2014→2026):  {gdp_g:+7.1f}%  │")
    print(f"  │ Per-capita GDP growth:         {pc_g:+7.1f}%  │")
    print(f"  │ PPP-adj per-capita growth:     {ppp_g:+7.1f}%  │")
    print(f"  │ Area: {area_km2:.0f} km²  ·  Pop 2026: {pop26:.2f}M{'':<8}│")
    print(f"  └─────────────────────────────────────────┘")

    # 8. Charts
    city_dir = OUTPUT_DIR / city_name.lower().replace(" ", "_")
    plot_city_report(series, save_dir=str(city_dir), events=cfg["events"])
    print(f"  Charts → {city_dir}/")


# ─────────────────────────────────────────────────────────────────────────────
# Greater Hyderabad (Hyderabad + Rangareddi union)
# ─────────────────────────────────────────────────────────────────────────────
print(f"\n{'='*60}")
print("  Greater Hyderabad (Hyderabad ∪ Rangareddi)")
print(f"{'='*60}")

cfg = GREATER_HYDERABAD
print("  Merging Hyderabad + Rangareddi boundaries…")
geom = resolve_union_geometry(cfg["districts"])
area_km2 = geom.area(maxError=100).getInfo() / 1e6
print(f"  Combined area: {area_km2:.0f} km²")

print(f"  Fetching VIIRS {START_YR}–{END_YR}…")
df = extract_viirs(geom, START_YR, END_YR)
print(f"  Fetched {len(df)} monthly observations")
print(f"  Radiance range: {df['radiance_raw'].min():.2f} – {df['radiance_raw'].max():.2f} nW/cm²/sr")

df = correct_cloud_bias(df, cf_threshold=CF_THRESH)
stats = correction_stats(df)
print(f"  Cloud correction: {stats['n_corrected']} months corrected "
      f"(mean uplift {stats['mean_uplift_pct']:.1f}%, max {stats['max_uplift_pct']:.1f}%)")

lta = LightingTechConfig(
    country_code="IND",
    apply_led_correction=True,
    apply_electrification_correction=False,
    apply_efficiency_dampening=True,
    custom_led_penetration=LED_PENETRATION[cfg["state_led"]],
)
df = apply_lighting_tech_adjustment(df, lta)
lta_sum = lta_correction_summary(df)
peak = lta_sum.loc[lta_sum["uplift_pct"].idxmax()]
print(f"  LTA: peak correction {peak['uplift_pct']:.1f}% in {int(peak['year'])}")

target_years = list(range(START_YR, END_YR + 1))
pop = interpolate_population(cfg["population"], target_years)
ppp = interpolate_population(PPP_INDIA, target_years)

df = compute_all_metrics(
    df, base_year=BASE_YR,
    population_by_year=pop,
    ppp_factors=ppp,
    radiance_col="radiance_lta",
    elasticity=ELASTICITY,
)

greater_hyd = RadianceSeries(
    city="Greater Hyderabad",
    df=df,
    geometry_area_km2=area_km2,
    population_by_year=pop,
    ppp_factors=ppp,
    metadata={
        "base_year": BASE_YR, "start_year": START_YR, "end_year": END_YR,
        "elasticity": ELASTICITY, "lta_applied": True,
        "state": cfg["state_led"], "source": "VIIRS/GEE (real)",
        "districts": "Hyderabad + Rangareddi",
    },
)
all_series["Greater Hyderabad"] = greater_hyd

gdp_g = total_growth_pct(greater_hyd, "gdp_proxy")
pc_g  = total_growth_pct(greater_hyd, "gdp_per_capita")
ppp_g = total_growth_pct(greater_hyd, "gdp_ppp_per_capita")
pop26 = pop[2026] / 1e6

print(f"\n  ┌─────────────────────────────────────────┐")
print(f"  │ {'Greater Hyderabad':^41}│")
print(f"  ├─────────────────────────────────────────┤")
print(f"  │ GDP proxy growth (2014→2026):  {gdp_g:+7.1f}%  │")
print(f"  │ Per-capita GDP growth:         {pc_g:+7.1f}%  │")
print(f"  │ PPP-adj per-capita growth:     {ppp_g:+7.1f}%  │")
print(f"  │ Area: {area_km2:.0f} km²  ·  Pop 2026: {pop26:.2f}M{'':<4}│")
print(f"  └─────────────────────────────────────────┘")

plot_city_report(greater_hyd, save_dir=str(OUTPUT_DIR / "greater_hyderabad"),
                 events=cfg["events"])
print(f"  Charts → {OUTPUT_DIR}/greater_hyderabad/")


# ─────────────────────────────────────────────────────────────────────────────
# Comparison + rankings
# ─────────────────────────────────────────────────────────────────────────────
series_list = list(all_series.values())

print(f"\n{'='*60}")
print("  COMPARATIVE RANKINGS (real satellite data)")
print(f"{'='*60}")

ranking_pc    = rank_cities(series_list, metric="per_capita_growth", top_n=3, bottom_n=1)
ranking_total = rank_cities(series_list, metric="total_growth",      top_n=3, bottom_n=1)

print("\n  Per-Capita Growth:")
for _, r in ranking_pc.iterrows():
    print(f"    #{int(r['rank'])}  {r['city']:15s}  {r['per_capita_growth']:+.1f}%")

print("\n  Total GDP Proxy Growth:")
for _, r in ranking_total.iterrows():
    print(f"    #{int(r['rank'])}  {r['city']:15s}  {r['total_growth']:+.1f}%")

fig_dash = plot_city_comparison(
    series_list,
    save_path=str(OUTPUT_DIR / "comparison_dashboard.png"),
)
plot_rankings(
    ranking_pc, metric="per_capita_growth",
    title="Bhubaneswar · Kolkata · Hyderabad — Per-Capita GDP Growth (real VIIRS)",
    save_path=str(OUTPUT_DIR / "rankings_per_capita.png"),
)
plot_rankings(
    ranking_total, metric="total_growth",
    title="Bhubaneswar · Kolkata · Hyderabad — Total GDP Proxy Growth (real VIIRS)",
    save_path=str(OUTPUT_DIR / "rankings_total.png"),
)

print(f"\n  Comparison dashboard → {OUTPUT_DIR}/comparison_dashboard.png")
print(f"  Rankings            → {OUTPUT_DIR}/rankings_*.png")
print(f"\n{'='*60}")
print(f"  Done. All charts in: {OUTPUT_DIR.resolve()}/")
print(f"{'='*60}")
