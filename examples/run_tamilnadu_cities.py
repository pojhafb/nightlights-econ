"""Real GEE extraction: Tamil Nadu major cities (2014–2026)."""

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
from nightlights_econ.plotting import plot_city_report, plot_city_comparison, plot_rankings, plot_shock_resilience
from nightlights_econ.rankings import rank_cities
from nightlights_econ.utils import interpolate_population

PROJECT = "nightlights-analysis"
START_YR, END_YR, BASE_YR = 2014, 2026, 2014
SCALE, CF_THRESH, ELASTICITY = 500, 8, 0.95
RAD_CAP = 100.0
OUTPUT_DIR = Path("./reports/tamilnadu_cities")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

print("Initializing GEE…")
ee.Initialize(project=PROJECT)
print("GEE OK\n")

CITIES = {
    "Chennai": {
        "admin2": "Chennai", "admin1": "Tamil Nadu", "country": "India",
        # Chennai city 2011: 7.09M; UA: 8.7M
        "population": {2001: 6_560_242, 2011: 7_088_000, 2021: 8_200_000, 2026: 9_000_000},
        "events": [
            {"date": "2015-11-01", "label": "Chennai Floods"},
            {"date": "2021-05-02", "label": "DMK wins state election"},
        ],
    },
    "Coimbatore": {
        "admin2": "Coimbatore", "admin1": "Tamil Nadu", "country": "India",
        # Coimbatore UA 2011: 2.1M; district: 3.46M
        "population": {2001: 2_856_954, 2011: 3_458_045, 2021: 4_000_000, 2026: 4_450_000},
        "events": [
            {"date": "2022-10-23", "label": "Kottai Eswaran temple blast"},
        ],
    },
    "Madurai": {
        "admin2": "Madurai", "admin1": "Tamil Nadu", "country": "India",
        # Madurai UA 2011: 1.46M; district: 3.04M
        "population": {2001: 2_560_943, 2011: 3_038_252, 2021: 3_500_000, 2026: 3_850_000},
        "events": [],
    },
    "Tiruchirappalli": {
        "admin2": "Tiruchchirappalli", "admin1": "Tamil Nadu", "country": "India",
        # Trichy UA 2011: ~1.02M; district: 2.71M
        "population": {2001: 2_422_083, 2011: 2_713_858, 2021: 3_100_000, 2026: 3_400_000},
        "events": [],
    },
    "Salem": {
        "admin2": "Salem", "admin1": "Tamil Nadu", "country": "India",
        # Salem city 2011: 831K (borderline); district: 3.48M
        "population": {2001: 2_989_632, 2011: 3_482_056, 2021: 3_950_000, 2026: 4_300_000},
        "events": [],
    },
    "Tirunelveli": {
        "admin2": "Tirunelveli Kattabo", "admin1": "Tamil Nadu", "country": "India",
        # Tirunelveli-Palayamkottai UA 2011: ~474K; district: 3.07M
        "population": {2001: 2_804_437, 2011: 3_077_716, 2021: 3_400_000, 2026: 3_700_000},
        "events": [],
    },
    "Vellore": {
        "admin2": "Vellore", "admin1": "Tamil Nadu", "country": "India",
        # Vellore city 2011: ~423K; district: 3.93M
        "population": {2001: 3_483_595, 2011: 3_936_331, 2021: 4_400_000, 2026: 4_800_000},
        "events": [],
    },
    "Erode": {
        "admin2": "Erode", "admin1": "Tamil Nadu", "country": "India",
        # Erode city 2011: ~214K; district: 2.25M (textile hub)
        "population": {2001: 1_993_403, 2011: 2_251_744, 2021: 2_550_000, 2026: 2_750_000},
        "events": [],
    },
}

# Tamil Nadu LED penetration (aggressive SLNP rollout — TN was early adopter)
TN_LED = {
    2014: 0.02, 2015: 0.07, 2016: 0.18, 2017: 0.35, 2018: 0.55,
    2019: 0.70, 2020: 0.80, 2021: 0.87, 2022: 0.91, 2023: 0.94,
    2024: 0.96, 2025: 0.97, 2026: 0.97,
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
                             custom_led_penetration=TN_LED)
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
    plot_city_report(series, save_dir=str(OUTPUT_DIR / city_name.lower().replace(" ","_")),
                     events=cfg["events"])
    print(f"  Charts saved.")

# Rankings
series_list = list(all_series.values())
print(f"\n{'='*60}\n  TAMIL NADU RANKINGS\n{'='*60}")
rank_pc    = rank_cities(series_list, metric="per_capita_growth", top_n=8, bottom_n=1)
rank_total = rank_cities(series_list, metric="total_growth",      top_n=8, bottom_n=1)
print("\n  Per-Capita Growth (2014→2026):")
for _, r in rank_pc.iterrows():
    print(f"    #{int(r['rank'])}  {r['city']:20s}  {r['per_capita_growth']:+.1f}%")
print("\n  Total GDP Proxy Growth:")
for _, r in rank_total.iterrows():
    print(f"    #{int(r['rank'])}  {r['city']:20s}  {r['total_growth']:+.1f}%")

# Chennai floods shock
print(f"\n{'='*60}\n  SHOCK: Chennai Floods (Nov 2015)\n{'='*60}")
shock = shock_analysis(all_series["Chennai"], event_date="2015-11-01", window_months=12)
if "error" not in shock:
    print(f"  Post-flood change: {shock['drop_pct']:+.1f}%  |  Resilience: {shock['resilience_score']:.0f}/100")

plot_city_comparison(series_list[:6], save_path=str(OUTPUT_DIR / "tn_top6_comparison_dashboard.png"))
plot_rankings(rank_pc, metric="per_capita_growth",
              title="Tamil Nadu Cities: Per-Capita GDP Growth 2014–2026 (real VIIRS)",
              save_path=str(OUTPUT_DIR / "tn_rankings_per_capita.png"))
plot_rankings(rank_total, metric="total_growth",
              title="Tamil Nadu Cities: Total GDP Proxy Growth 2014–2026 (real VIIRS)",
              save_path=str(OUTPUT_DIR / "tn_rankings_total.png"))
print(f"\n  Done. Charts in: {OUTPUT_DIR.resolve()}/")
