"""Real GEE extraction: Karnataka major cities (2014–2026)."""

import matplotlib; matplotlib.use("Agg")
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

PROJECT = "nightlights-analysis"
START_YR, END_YR, BASE_YR = 2014, 2026, 2014
SCALE, CF_THRESH, ELASTICITY = 500, 8, 0.95
RAD_CAP = 100.0
OUTPUT_DIR = Path("./reports/karnataka_cities")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

print("Initializing GEE…")
ee.Initialize(project=PROJECT)
print("GEE OK\n")

CITIES = {
    "Bengaluru": {
        "admin2": "Bangalore Urban", "admin1": "Karnataka", "country": "India",
        # City pop 2011: 8.4M; district: 9.6M
        "population": {2001: 6_537_124, 2011: 9_621_551, 2021: 13_000_000, 2026: 15_000_000},
        "events": [
            {"date": "2014-05-26", "label": "Modi govt. Day 1"},
            {"date": "2022-07-01", "label": "State election build-up"},
        ],
    },
    "Mysuru": {
        "admin2": "Mysore", "admin1": "Karnataka", "country": "India",
        # Mysore city 2011: 887K; UA ~0.9M; district: 3.0M
        "population": {2001: 2_624_911, 2011: 3_001_127, 2021: 3_400_000, 2026: 3_750_000},
        "events": [
            {"date": "2023-05-01", "label": "Congress govt. takes charge"},
        ],
    },
    "Hubli-Dharwad": {
        "admin2": "Dharwad", "admin1": "Karnataka", "country": "India",
        # Hubli-Dharwad UA 2011: 943K; district: 1.85M
        "population": {2001: 1_604_286, 2011: 1_847_023, 2021: 2_100_000, 2026: 2_300_000},
        "events": [
            {"date": "2020-01-29", "label": "Hubballi-Dharwad BRTS"},
        ],
    },
    "Belagavi": {
        "admin2": "Belgaum", "admin1": "Karnataka", "country": "India",
        # Belagavi city 2011: ~488K; district: 4.78M
        "population": {2001: 4_214_505, 2011: 4_779_661, 2021: 5_300_000, 2026: 5_700_000},
        "events": [],
    },
    "Mangaluru": {
        "admin2": "Dakshin Kannad", "admin1": "Karnataka", "country": "India",
        # Mangalore UA 2011: ~623K; district: 2.08M
        "population": {2001: 1_897_730, 2011: 2_083_625, 2021: 2_300_000, 2026: 2_500_000},
        "events": [
            {"date": "2020-01-19", "label": "CAA protests"},
        ],
    },
    "Kalaburagi": {
        "admin2": "Gulbarga", "admin1": "Karnataka", "country": "India",
        # Gulbarga city 2011: ~532K; district: 2.56M
        "population": {2001: 2_152_213, 2011: 2_564_892, 2021: 2_900_000, 2026: 3_150_000},
        "events": [],
    },
}

# Karnataka LED penetration (SLNP + state RGGVY rollout)
KA_LED = {
    2014: 0.01, 2015: 0.04, 2016: 0.12, 2017: 0.25, 2018: 0.47,
    2019: 0.64, 2020: 0.76, 2021: 0.84, 2022: 0.90, 2023: 0.93,
    2024: 0.95, 2025: 0.96, 2026: 0.97,
}

PPP_INDIA = {
    2014: 18.17, 2015: 18.69, 2016: 19.12, 2017: 19.58, 2018: 20.22,
    2019: 21.01, 2020: 21.87, 2021: 22.40, 2022: 23.19, 2023: 24.02,
    2024: 24.85, 2025: 25.70, 2026: 26.55,
}

def extract_viirs(geometry, start_yr, end_yr):
    col = (ee.ImageCollection("NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG")
           .filterDate(f"{start_yr}-01-01", f"{end_yr+1}-01-01")
           .filterBounds(geometry))
    images = col.toList(col.size())
    n = col.size().getInfo()
    print(f"    {n} monthly images")
    records = []
    for i in range(n):
        img = ee.Image(images.get(i))
        date = pd.Timestamp(img.get("system:time_start").getInfo(), unit="ms")
        result = (img.select("avg_rad").min(ee.Image.constant(RAD_CAP))
                    .rename("avg_rad").addBands(img.select("cf_cvg").rename("cf_cvg"))
                    .reduceRegion(ee.Reducer.mean(), geometry, SCALE, maxPixels=1e9).getInfo())
        records.append({
            "date": date, "year": date.year, "month": date.month,
            "radiance_raw": float(result.get("avg_rad") or float("nan")),
            "cf_obs": float(result.get("cf_cvg") or float("nan")),
        })
        if (i+1) % 12 == 0:
            print(f"      … {i+1}/{n}")
    return pd.DataFrame(records).sort_values("date").reset_index(drop=True)

gaul = ee.FeatureCollection("FAO/GAUL/2015/level2")
all_series = {}

for city_name, cfg in CITIES.items():
    print(f"\n{'='*60}\n  {city_name}\n{'='*60}")
    geom = (gaul.filter(ee.Filter.eq("ADM2_NAME", cfg["admin2"]))
                .filter(ee.Filter.eq("ADM1_NAME", cfg["admin1"]))
                .filter(ee.Filter.eq("ADM0_NAME", cfg["country"]))
                .first().geometry())
    area_km2 = geom.area(maxError=100).getInfo() / 1e6
    print(f"  Area: {area_km2:.0f} km²")

    df = extract_viirs(geom, START_YR, END_YR)
    print(f"  {len(df)} months  |  {df['radiance_raw'].min():.2f}–{df['radiance_raw'].max():.2f} nW/cm²/sr")

    df = correct_cloud_bias(df, cf_threshold=CF_THRESH)
    s = correction_stats(df)
    print(f"  Cloud: {s['n_corrected']} months corrected, mean uplift {s['mean_uplift_pct']:.1f}%")

    lta = LightingTechConfig(country_code="IND", apply_led_correction=True,
                             apply_electrification_correction=False, apply_efficiency_dampening=True,
                             custom_led_penetration=KA_LED)
    df = apply_lighting_tech_adjustment(df, lta)
    peak = lta_correction_summary(df).pipe(lambda d: d.loc[d["uplift_pct"].idxmax()])
    print(f"  LTA: peak {peak['uplift_pct']:.1f}% in {int(peak['year'])}")

    years = list(range(START_YR, END_YR+1))
    pop = interpolate_population(cfg["population"], years)
    ppp = interpolate_population(PPP_INDIA, years)
    df = compute_all_metrics(df, base_year=BASE_YR, population_by_year=pop, ppp_factors=ppp,
                             radiance_col="radiance_lta", elasticity=ELASTICITY)

    series = RadianceSeries(city=city_name, df=df, geometry_area_km2=area_km2,
                            population_by_year=pop, ppp_factors=ppp,
                            metadata={"base_year": BASE_YR, "lta_applied": True, "source": "VIIRS/GEE"})
    all_series[city_name] = series

    gdp_g, pc_g, ppp_g = (total_growth_pct(series, c) for c in ["gdp_proxy","gdp_per_capita","gdp_ppp_per_capita"])
    print(f"\n  ┌─────────────────────────────────────────┐")
    print(f"  │ {city_name:^41}│")
    print(f"  ├─────────────────────────────────────────┤")
    print(f"  │ GDP proxy growth:    {gdp_g:+7.1f}%              │")
    print(f"  │ Per-capita growth:   {pc_g:+7.1f}%              │")
    print(f"  │ PPP-adj per-capita:  {ppp_g:+7.1f}%              │")
    print(f"  │ Area {area_km2:.0f} km²  Pop 2026: {pop[2026]/1e6:.1f}M        │")
    print(f"  └─────────────────────────────────────────┘")
    plot_city_report(series, save_dir=str(OUTPUT_DIR / city_name.lower().replace("-","_").replace(" ","_")),
                     events=cfg["events"])
    print(f"  Charts saved.")

# Rankings
series_list = list(all_series.values())
print(f"\n{'='*60}\n  KARNATAKA RANKINGS\n{'='*60}")
rank_pc    = rank_cities(series_list, metric="per_capita_growth", top_n=6, bottom_n=1)
rank_total = rank_cities(series_list, metric="total_growth",      top_n=6, bottom_n=1)
print("\n  Per-Capita Growth (2014→2026):")
for _, r in rank_pc.iterrows():
    print(f"    #{int(r['rank'])}  {r['city']:20s}  {r['per_capita_growth']:+.1f}%")
print("\n  Total GDP Proxy Growth:")
for _, r in rank_total.iterrows():
    print(f"    #{int(r['rank'])}  {r['city']:20s}  {r['total_growth']:+.1f}%")

plot_city_comparison(series_list, save_path=str(OUTPUT_DIR / "karnataka_comparison_dashboard.png"))
plot_rankings(rank_pc, metric="per_capita_growth",
              title="Karnataka Cities: Per-Capita GDP Growth 2014–2026 (real VIIRS)",
              save_path=str(OUTPUT_DIR / "karnataka_rankings_per_capita.png"))
plot_rankings(rank_total, metric="total_growth",
              title="Karnataka Cities: Total GDP Proxy Growth 2014–2026 (real VIIRS)",
              save_path=str(OUTPUT_DIR / "karnataka_rankings_total.png"))
print(f"\n  Done. Charts in: {OUTPUT_DIR.resolve()}/")
