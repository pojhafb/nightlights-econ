"""
Real GEE extraction: Varanasi, Lucknow, Ghaziabad, Allahabad/Prayagraj (2014–2026).
All are in Uttar Pradesh — same LED penetration curve, elasticity 0.95.
"""

import matplotlib
matplotlib.use("Agg")

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

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

PROJECT    = "nightlights-analysis"
START_YR   = 2014
END_YR     = 2026
BASE_YR    = 2014
SCALE      = 500
CF_THRESH  = 8
ELASTICITY = 0.95
OUTPUT_DIR = Path("./reports/up_cities")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

print("Initializing GEE…")
ee.Initialize(project=PROJECT)
print("GEE OK\n")

# ─────────────────────────────────────────────────────────────────────────────
# City definitions
# ─────────────────────────────────────────────────────────────────────────────
CITIES = {
    "Varanasi": {
        "admin2": "Varanasi",
        "admin1": "Uttar Pradesh",
        "country": "India",
        "population": {2001: 3_138_671, 2011: 3_676_841, 2021: 4_300_000, 2026: 4_750_000},
        "events": [
            {"date": "2014-05-16", "label": "Modi wins from Varanasi"},
            {"date": "2021-11-13", "label": "Kashi Vishwanath Corridor"},
        ],
    },
    "Lucknow": {
        "admin2": "Lucknow",
        "admin1": "Uttar Pradesh",
        "country": "India",
        "population": {2001: 3_647_834, 2011: 4_588_455, 2021: 5_600_000, 2026: 6_300_000},
        "events": [
            {"date": "2017-03-19", "label": "Yogi govt. takes charge"},
            {"date": "2022-03-25", "label": "Yogi re-elected"},
        ],
    },
    "Ghaziabad": {
        "admin2": "Ghaziabad",
        "admin1": "Uttar Pradesh",
        "country": "India",
        "population": {2001: 3_290_586, 2011: 4_661_452, 2021: 5_800_000, 2026: 6_600_000},
        "events": [
            {"date": "2019-12-01", "label": "Delhi-Meerut Expressway"},
            {"date": "2023-04-01", "label": "Delhi-NCR expansion"},
        ],
    },
    "Allahabad": {
        "admin2": "Allahabad",
        "admin1": "Uttar Pradesh",
        "country": "India",
        "population": {2001: 4_923_756, 2011: 5_954_391, 2021: 7_000_000, 2026: 7_800_000},
        "events": [
            {"date": "2018-10-16", "label": "Renamed Prayagraj"},
            {"date": "2019-01-15", "label": "Kumbh Mela 2019"},
            {"date": "2025-01-13", "label": "Maha Kumbh 2025"},
        ],
    },
}

# UP LED penetration (SLNP — aggressive rollout under state govt)
UP_LED = {
    2014: 0.01, 2015: 0.03, 2016: 0.08, 2017: 0.20, 2018: 0.38,
    2019: 0.56, 2020: 0.70, 2021: 0.80, 2022: 0.87, 2023: 0.91,
    2024: 0.94, 2025: 0.95, 2026: 0.96,
}

PPP_INDIA = {
    2014: 18.17, 2015: 18.69, 2016: 19.12, 2017: 19.58, 2018: 20.22,
    2019: 21.01, 2020: 21.87, 2021: 22.40, 2022: 23.19, 2023: 24.02,
    2024: 24.85, 2025: 25.70, 2026: 26.55,
}

RAD_CAP = 100.0


def extract_viirs(geometry, start_yr, end_yr):
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
        result = (
            rad_img.rename("avg_rad")
                   .addBands(img.select("cf_cvg").rename("cf_cvg"))
                   .reduceRegion(
                       reducer=ee.Reducer.mean(),
                       geometry=geometry,
                       scale=SCALE,
                       maxPixels=1e9,
                   ).getInfo()
        )
        rad_val = result.get("avg_rad")
        cf_val  = result.get("cf_cvg")
        records.append({
            "date":         date,
            "year":         date.year,
            "month":        date.month,
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
gaul = ee.FeatureCollection("FAO/GAUL/2015/level2")

for city_name, cfg in CITIES.items():
    print(f"\n{'='*60}")
    print(f"  {city_name}")
    print(f"{'='*60}")

    geom = (gaul
            .filter(ee.Filter.eq("ADM2_NAME", cfg["admin2"]))
            .filter(ee.Filter.eq("ADM1_NAME", cfg["admin1"]))
            .filter(ee.Filter.eq("ADM0_NAME", cfg["country"]))
            .first().geometry())
    area_km2 = geom.area(maxError=100).getInfo() / 1e6
    print(f"  Area: {area_km2:.0f} km²")

    print(f"  Fetching VIIRS {START_YR}–{END_YR}…")
    df = extract_viirs(geom, START_YR, END_YR)
    print(f"  Fetched {len(df)} months  |  radiance {df['radiance_raw'].min():.2f}–{df['radiance_raw'].max():.2f} nW/cm²/sr")

    df = correct_cloud_bias(df, cf_threshold=CF_THRESH)
    s = correction_stats(df)
    print(f"  Cloud correction: {s['n_corrected']} months corrected (mean uplift {s['mean_uplift_pct']:.1f}%)")

    lta = LightingTechConfig(
        country_code="IND",
        apply_led_correction=True,
        apply_electrification_correction=False,
        apply_efficiency_dampening=True,
        custom_led_penetration=UP_LED,
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

    series = RadianceSeries(
        city=city_name,
        df=df,
        geometry_area_km2=area_km2,
        population_by_year=pop,
        ppp_factors=ppp,
        metadata={
            "base_year": BASE_YR, "start_year": START_YR, "end_year": END_YR,
            "elasticity": ELASTICITY, "lta_applied": True, "source": "VIIRS/GEE (real)",
        },
    )
    all_series[city_name] = series

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

    city_dir = OUTPUT_DIR / city_name.lower().replace(" ", "_")
    plot_city_report(series, save_dir=str(city_dir), events=cfg["events"])
    print(f"  Charts → {city_dir}/")


# ─────────────────────────────────────────────────────────────────────────────
# Rankings + comparison
# ─────────────────────────────────────────────────────────────────────────────
series_list = list(all_series.values())

print(f"\n{'='*60}")
print("  RANKINGS — Uttar Pradesh cities (real VIIRS)")
print(f"{'='*60}")

ranking_pc    = rank_cities(series_list, metric="per_capita_growth", top_n=4, bottom_n=1)
ranking_total = rank_cities(series_list, metric="total_growth",      top_n=4, bottom_n=1)

print("\n  Per-Capita Growth (2014→2026):")
for _, r in ranking_pc.iterrows():
    print(f"    #{int(r['rank'])}  {r['city']:15s}  {r['per_capita_growth']:+.1f}%")

print("\n  Total GDP Proxy Growth:")
for _, r in ranking_total.iterrows():
    print(f"    #{int(r['rank'])}  {r['city']:15s}  {r['total_growth']:+.1f}%")

# Shock: Kashi Vishwanath Corridor on Varanasi
print(f"\n{'='*60}")
print("  SHOCK: Kashi Vishwanath Corridor (Nov 2021) — Varanasi")
print(f"{'='*60}")
shock = shock_analysis(all_series["Varanasi"], event_date="2021-11-13", window_months=18)
if "error" not in shock:
    print(f"  Post-inauguration change: {shock['drop_pct']:+.1f}%")
    print(f"  Resilience score: {shock['resilience_score']:.0f}/100")

# Shock: Kumbh Mela 2019 on Allahabad
print(f"\n{'='*60}")
print("  SHOCK: Kumbh Mela 2019 — Allahabad/Prayagraj")
print(f"{'='*60}")
shock_kmb = shock_analysis(all_series["Allahabad"], event_date="2019-01-15", window_months=12)
if "error" not in shock_kmb:
    print(f"  Post-Kumbh change: {shock_kmb['drop_pct']:+.1f}%")
    print(f"  Resilience score: {shock_kmb['resilience_score']:.0f}/100")

# Charts
from nightlights_econ.plotting import plot_shock_resilience
plot_city_comparison(
    series_list,
    save_path=str(OUTPUT_DIR / "up_cities_comparison_dashboard.png"),
)
plot_rankings(
    ranking_pc, metric="per_capita_growth",
    title="UP Cities: Per-Capita GDP Growth 2014–2026 (real VIIRS + LED correction)",
    save_path=str(OUTPUT_DIR / "up_cities_rankings_per_capita.png"),
)
plot_rankings(
    ranking_total, metric="total_growth",
    title="UP Cities: Total GDP Proxy Growth 2014–2026 (real VIIRS + LED correction)",
    save_path=str(OUTPUT_DIR / "up_cities_rankings_total.png"),
)

shock_results = []
for s_name, evt_date, evt_label in [
    ("Varanasi",  "2021-11-13", "Kashi Vishwanath Corridor"),
    ("Allahabad", "2019-01-15", "Kumbh Mela 2019"),
]:
    r = shock_analysis(all_series[s_name], event_date=evt_date, window_months=18)
    if "error" not in r:
        r["city"] = s_name
        shock_results.append(r)

if shock_results:
    plot_shock_resilience(
        shock_results,
        event_name="Key events",
        save_path=str(OUTPUT_DIR / "up_cities_shock.png"),
    )

print(f"\n{'='*60}")
print(f"  Done. Charts in: {OUTPUT_DIR.resolve()}/")
print(f"{'='*60}")
