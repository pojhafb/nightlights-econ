"""
Rural & Non-Urban Nighttime Lights Analysis

Two approaches:
  Option 1 — District Donut: For districts we've already analyzed as cities,
    re-extract VIIRS using only the non-urban pixels (GHS-SMOD rural mask).
    Shows how the rural ring around major cities has grown vs the city core.

  Option 3 — Thematic Rural Clusters: Specific agrarian stress / tribal /
    drought-affected district groups:
      - Vidarbha (Maharashtra cotton belt, farmer distress)
      - Bundelkhand (UP+MP drought belt)
      - KBK region (Kalahandi-Bolangir-Koraput, Odisha's poorest)
      - Tribal belt (Jharkhand/Chhattisgarh)
      - Marathwada (Maharashtra drought + sugar)

GHS-SMOD classification used for Option 1:
  Code 10: water bodies
  Code 11: very low density rural
  Code 12: low density rural
  Code 13: rural cluster
  Code 21: suburban / peri-urban
  Code 22: semi-dense urban cluster
  Code 23: dense urban cluster
  Code 30: urban centre
  -> We keep codes <= 13 as "rural", codes 21-30 as "urban"
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

from nightlights_econ.cache import geometry_key, get_cached, save_to_cache
from nightlights_econ.extractor import extract_for_district
from nightlights_econ.cloud_correction import correct_cloud_bias, correction_stats
from nightlights_econ.gdp_proxy import compute_all_metrics
from nightlights_econ.lighting_tech import LightingTechConfig, apply_lighting_tech_adjustment
from nightlights_econ.core import RadianceSeries
from nightlights_econ.analysis import total_growth_pct
from nightlights_econ.india_census import district_population_series
from nightlights_econ.utils import interpolate_population
from nightlights_econ.plotting import plot_city_comparison, plot_rankings, plot_city_report
from nightlights_econ.rankings import rank_cities

PROJECT    = "nightlights-analysis"
START_YR   = 2014
END_YR     = 2026
BASE_YR    = 2014
SCALE      = 500
CF_THRESH  = 8
ELASTICITY = 0.95
MAX_WORKERS = 5
OUTPUT_DIR = Path("./reports/rural_analysis")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# GHS-SMOD: codes <= 13 are rural (very low / low density / rural cluster)
SMOD_RURAL_MAX_CODE = 13

PPP_INDIA = {
    2014: 18.17, 2015: 18.69, 2016: 19.12, 2017: 19.58, 2018: 20.22,
    2019: 21.01, 2020: 21.87, 2021: 22.40, 2022: 23.19, 2023: 24.02,
    2024: 24.85, 2025: 25.70, 2026: 26.55,
}
DEFAULT_LED = {
    # LED penetration is much lower in rural areas — SLNP targeted municipal lights
    2014: 0.00, 2015: 0.01, 2016: 0.02, 2017: 0.05, 2018: 0.10,
    2019: 0.18, 2020: 0.28, 2021: 0.38, 2022: 0.48, 2023: 0.57,
    2024: 0.64, 2025: 0.70, 2026: 0.74,
}

print("Initializing GEE...")
ee.Initialize(project=PROJECT)
gaul = ee.FeatureCollection("FAO/GAUL/2015/level2")
smod_2020 = ee.Image("JRC/GHSL/P2023A/GHS_SMOD/2020").select("smod_code")
print("GEE OK\n")


# ─────────────────────────────────────────────────────────────────────────────
# OPTION 1: District Donut — rural mask via GHS-SMOD
# ─────────────────────────────────────────────────────────────────────────────

# Districts to "donut": major cities we analyzed whose districts contain
# significant rural hinterland worth measuring separately
DONUT_DISTRICTS = [
    # (display_urban, display_rural, admin2, admin1, census_state)
    ("Pune (city)",    "Pune (rural hinterland)", "Pune",          "Maharashtra",  "Maharashtra"),
    ("Lucknow (city)", "Lucknow (hinterland)",    "Lucknow",       "Uttar Pradesh","Uttar Pradesh"),
    ("Varanasi (city)","Varanasi (rural)",        "Varanasi",      "Uttar Pradesh","Uttar Pradesh"),
    ("Jaipur (city)",  "Jaipur (rural)",          "Jaipur",        "Rajasthan",    "Rajasthan"),
    ("Bhubaneswar (city)","Bhubaneswar (rural)",  "Khordha",       "Orissa",       "Orissa"),
    ("Coimbatore (city)","Coimbatore (rural)",    "Coimbatore",    "Tamil Nadu",   "Tamil Nadu"),
    ("Patna (city)",   "Patna (rural)",           "Patna",         "Bihar",        "Bihar"),
]


def extract_viirs_with_mask(geometry, geo_key_suffix, mask_image,
                             start_yr, end_yr, scale=500):
    """Extract VIIRS mean over pixels matching a mask, with caching."""
    full_key = f"masked:{geo_key_suffix}"

    cached = get_cached(full_key, start_yr, end_yr, scale)
    if cached is not None:
        return cached

    col = (ee.ImageCollection("NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG")
           .filterDate(f"{start_yr}-01-01", f"{end_yr+1}-01-01")
           .filterBounds(geometry))

    def reduce_img(img):
        # Apply mask before reducing
        masked_rad = img.select("avg_rad").min(ee.Image.constant(100)).updateMask(mask_image)
        masked_cf  = img.select("cf_cvg").updateMask(mask_image)
        reduced = (masked_rad.rename("avg_rad")
                             .addBands(masked_cf.rename("cf_cvg"))
                             .reduceRegion(ee.Reducer.mean(), geometry, scale, maxPixels=1e9))
        return ee.Feature(None, {
            "time":    img.get("system:time_start"),
            "avg_rad": reduced.get("avg_rad"),
            "cf_cvg":  reduced.get("cf_cvg"),
        })

    fc = col.map(reduce_img).getInfo()
    records = []
    for feat in fc.get("features", []):
        props = feat["properties"]
        ts = props.get("time")
        if not ts:
            continue
        date = pd.Timestamp(ts, unit="ms")
        records.append({
            "date": date, "year": date.year, "month": date.month,
            "radiance_raw": float(props["avg_rad"]) if props.get("avg_rad") is not None else float("nan"),
            "cf_obs":       float(props["cf_cvg"])  if props.get("cf_cvg")  is not None else float("nan"),
        })

    df = pd.DataFrame(records).sort_values("date").reset_index(drop=True)
    save_to_cache(full_key, start_yr, end_yr, scale, df)
    return df


def run_pipeline(df, state, admin2, label):
    """Cloud correct, LTA, GDP metrics -> RadianceSeries."""
    df = correct_cloud_bias(df.copy(), cf_threshold=CF_THRESH)
    lta = LightingTechConfig(
        country_code="IND", apply_led_correction=True,
        apply_electrification_correction=False, apply_efficiency_dampening=True,
        custom_led_penetration=DEFAULT_LED,
    )
    df = apply_lighting_tech_adjustment(df, lta)
    years = list(range(START_YR, END_YR + 1))
    pop = district_population_series(state, admin2, years)
    ppp = interpolate_population(PPP_INDIA, years)
    df = compute_all_metrics(df, base_year=BASE_YR, population_by_year=pop,
                             ppp_factors=ppp, radiance_col="radiance_lta",
                             elasticity=ELASTICITY)
    return RadianceSeries(
        city=label, df=df, geometry_area_km2=0.0,
        population_by_year=pop, ppp_factors=ppp,
        metadata={"base_year": BASE_YR, "lta_applied": True, "source": "VIIRS/GEE"},
    )


print("=" * 65)
print("  OPTION 1: District Donut (urban vs rural pixels)")
print("=" * 65)

donut_pairs = {}   # {admin2: (urban_series, rural_series)}
rural_mask  = smod_2020.lte(SMOD_RURAL_MAX_CODE)
urban_mask  = smod_2020.gt(SMOD_RURAL_MAX_CODE)

for disp_u, disp_r, admin2, admin1, census_state in DONUT_DISTRICTS:
    print(f"\n  {admin2} / {admin1}")

    geom = (gaul.filter(ee.Filter.eq("ADM2_NAME", admin2))
                .filter(ee.Filter.eq("ADM1_NAME", admin1))
                .filter(ee.Filter.eq("ADM0_NAME", "India"))
                .first().geometry())

    geo_key_base = geometry_key(admin2, admin1, "India")

    # Urban pixels
    print(f"    [urban pixels]...", end=" ", flush=True)
    df_urban = extract_viirs_with_mask(geom, f"urban:{geo_key_base}", urban_mask,
                                        START_YR, END_YR)
    print(f"{len(df_urban)} rows")

    # Rural pixels
    print(f"    [rural pixels]...", end=" ", flush=True)
    df_rural = extract_viirs_with_mask(geom, f"rural:{geo_key_base}", rural_mask,
                                        START_YR, END_YR)
    print(f"{len(df_rural)} rows")

    try:
        s_urban = run_pipeline(df_urban, census_state, admin2, disp_u)
        s_rural = run_pipeline(df_rural, census_state, admin2, disp_r)
        donut_pairs[admin2] = (s_urban, s_rural)

        g_u = total_growth_pct(s_urban, "gdp_per_capita")
        g_r = total_growth_pct(s_rural, "gdp_per_capita")
        diff = g_r - g_u
        faster = "rural faster" if diff > 0 else "urban faster"
        print(f"    Urban: {g_u:+.1f}%  Rural: {g_r:+.1f}%  ({faster} by {abs(diff):.1f}pp)")
    except Exception as e:
        print(f"    ERROR: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# OPTION 3: Thematic Rural Clusters
# ─────────────────────────────────────────────────────────────────────────────

RURAL_CLUSTERS = {
    "Vidarbha (Cotton Belt)": [
        ("Yavatmal",  "Maharashtra",  "Maharashtra"),
        ("Wardha",    "Maharashtra",  "Maharashtra"),
        ("Amravati",  "Maharashtra",  "Maharashtra"),
        ("Akola",     "Maharashtra",  "Maharashtra"),
        ("Washim",    "Maharashtra",  "Maharashtra"),
        ("Buldana",   "Maharashtra",  "Maharashtra"),   # GAUL: Buldana not Buldhana
    ],
    "Bundelkhand (Drought Belt)": [
        ("Jhansi",      "Uttar Pradesh",  "Uttar Pradesh"),
        ("Banda",       "Uttar Pradesh",  "Uttar Pradesh"),
        ("Lalitpur",    "Uttar Pradesh",  "Uttar Pradesh"),
        ("Hamirpur",    "Uttar Pradesh",  "Uttar Pradesh"),
        ("Mahoba",      "Uttar Pradesh",  "Uttar Pradesh"),
        ("Chhatarpur",  "Madhya Pradesh", "Madhya Pradesh"),
        ("Tikamgarh",   "Madhya Pradesh", "Madhya Pradesh"),
    ],
    "KBK Region (Odisha)": [
        ("Koraput",   "Orissa",  "Orissa"),
        ("Kalahandi", "Orissa",  "Orissa"),
        ("Nuapada",   "Orissa",  "Orissa"),
    ],
    "Tribal Belt (Jharkhand/CG)": [
        ("Pashchim Singhbhum", "Jharkhand",    "Jharkhand"),   # GAUL name for West Singhbhum
        ("Gumla",              "Jharkhand",    "Jharkhand"),
        ("Bastar",             "Chhattisgarh", "Chhattisgarh"),
        ("Dantewada",          "Chhattisgarh", "Chhattisgarh"),
    ],
    "Marathwada (Drought)": [
        ("Osmanabad", "Maharashtra",  "Maharashtra"),
        ("Latur",     "Maharashtra",  "Maharashtra"),
        ("Bid",       "Maharashtra",  "Maharashtra"),   # GAUL: Bid not Beed
        ("Nanded",    "Maharashtra",  "Maharashtra"),
    ],
}

print(f"\n{'='*65}")
print("  OPTION 3: Thematic Rural Clusters")
print(f"{'='*65}")

_lock = threading.Lock()


def fetch_rural_district(args):
    admin2, admin1, census_state = args
    key = geometry_key(admin2, admin1, "India")

    cached = get_cached(key, START_YR, END_YR, SCALE)
    if cached is not None:
        with _lock:
            print(f"    cached: {admin2}/{admin1}")
        return admin2, admin1, census_state, cached

    with _lock:
        print(f"    fetching: {admin2}/{admin1}...")
    try:
        df = extract_for_district(admin2, admin1, "India", START_YR, END_YR, SCALE)
        with _lock:
            print(f"    stored:  {admin2}/{admin1} ({len(df)} rows)")
        return admin2, admin1, census_state, df
    except Exception as e:
        with _lock:
            print(f"    FAILED:  {admin2}/{admin1} - {e}")
        return admin2, admin1, census_state, None


cluster_series = {}   # {cluster_name: list of RadianceSeries}

for cluster_name, districts in RURAL_CLUSTERS.items():
    print(f"\n  Cluster: {cluster_name}")

    # Fetch all districts in parallel
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(fetch_rural_district, d): d for d in districts}
        raw_data = {}
        for fut in as_completed(futures):
            admin2, admin1, census_state, df = fut.result()
            if df is not None:
                raw_data[(admin2, admin1, census_state)] = df

    # Run pipeline
    series_list = []
    for (admin2, admin1, census_state), df in raw_data.items():
        try:
            s = run_pipeline(df, census_state, admin2, f"{admin2}")
            series_list.append(s)
        except Exception as e:
            print(f"    Pipeline error {admin2}: {e}")

    cluster_series[cluster_name] = series_list

    if not series_list:
        print(f"    No data for {cluster_name}")
        continue

    # Aggregate cluster (mean across districts)
    growths = [total_growth_pct(s, "gdp_per_capita") for s in series_list]
    growths_valid = [g for g in growths if not np.isnan(g)]
    cluster_mean = np.mean(growths_valid) if growths_valid else float("nan")

    print(f"  Cluster mean per-capita growth: {cluster_mean:+.1f}%")
    for s, g in sorted(zip(series_list, growths), key=lambda x: x[1], reverse=True):
        print(f"    {s.city:20s}  {g:+.1f}%")


# ─────────────────────────────────────────────────────────────────────────────
# SUMMARY + CHARTS
# ─────────────────────────────────────────────────────────────────────────────
print(f"\n{'='*65}")
print("  SUMMARY")
print(f"{'='*65}")

# Urban vs Rural comparison table
print("\n  Option 1 - Urban vs Rural Growth (same district):")
print(f"  {'District':20s}  {'Urban':>8}  {'Rural':>8}  {'Diff':>8}  {'Winner':>12}")
print(f"  {'-'*60}")
for admin2, (s_u, s_r) in donut_pairs.items():
    g_u = total_growth_pct(s_u, "gdp_per_capita")
    g_r = total_growth_pct(s_r, "gdp_per_capita")
    diff = g_r - g_u
    winner = "RURAL" if diff > 0 else "urban"
    print(f"  {admin2:20s}  {g_u:>+7.1f}%  {g_r:>+7.1f}%  {diff:>+7.1f}pp  {winner:>12}")

# Cluster summary
print(f"\n  Option 3 - Rural Cluster Growth (2014-2026):")
cluster_means = {}
for cluster_name, series_list in cluster_series.items():
    if not series_list:
        continue
    growths = [total_growth_pct(s, "gdp_per_capita") for s in series_list]
    growths_valid = [g for g in growths if not np.isnan(g)]
    mean_g = np.mean(growths_valid) if growths_valid else float("nan")
    cluster_means[cluster_name] = mean_g
    print(f"  {cluster_name:35s}  {mean_g:>+7.1f}%")

# ── Generate charts ──
print(f"\n  Generating charts...")

# Chart 1: Urban vs Rural comparison bars
import matplotlib.pyplot as plt
import matplotlib
PALETTE = ["#1B4F72", "#27AE60", "#E74C3C", "#F39C12", "#8E44AD", "#2C3E50"]

fig, ax = plt.subplots(figsize=(14, 7))
districts_list = list(donut_pairs.keys())
x = np.arange(len(districts_list))
w = 0.35

urban_g = [total_growth_pct(donut_pairs[d][0], "gdp_per_capita") for d in districts_list]
rural_g = [total_growth_pct(donut_pairs[d][1], "gdp_per_capita") for d in districts_list]

ax.bar(x - w/2, urban_g, w, label="Urban pixels (GHS-SMOD code > 13)",
       color=PALETTE[0], alpha=0.9)
ax.bar(x + w/2, rural_g, w, label="Rural pixels (GHS-SMOD code <= 13)",
       color=PALETTE[1], alpha=0.9)

for i, (u, r) in enumerate(zip(urban_g, rural_g)):
    ax.text(i-w/2, u+2, f"{u:+.0f}%", ha="center", fontsize=8, color=PALETTE[0])
    ax.text(i+w/2, r+2, f"{r:+.0f}%", ha="center", fontsize=8, color=PALETTE[1])

ax.set_xticks(x)
ax.set_xticklabels(districts_list, rotation=20, ha="right", fontsize=10)
ax.set_ylabel("Per-Capita GDP Growth % (2014-2026)", fontsize=11)
ax.set_title("Urban Core vs Rural Hinterland: Per-Capita GDP Growth within Same District\n"
             "GHS Settlement Model used to separate urban/rural pixels",
             fontsize=12, fontweight="bold")
ax.legend(fontsize=10)
ax.axhline(0, color="#888", linewidth=0.8)
ax.set_facecolor("#FAFAFA")
ax.grid(True, axis="y", color="#E0E0E0")
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.annotate("Source: NASA VIIRS DNB / JRC GHS-SMOD / World Bank",
            xy=(0, -0.18), xycoords="axes fraction", fontsize=7.5, color="#777")
fig.tight_layout()
chart1 = str(OUTPUT_DIR / "donut_urban_vs_rural.png")
fig.savefig(chart1, dpi=150, bbox_inches="tight")
plt.close(fig)
print(f"  Chart -> {chart1}")

# Chart 2: Cluster ranking
if cluster_means:
    items = sorted(cluster_means.items(), key=lambda x: x[1])
    names = [x[0] for x in items]
    vals  = [x[1] for x in items]

    fig, ax = plt.subplots(figsize=(12, 6))
    colors = [PALETTE[1] if v < 150 else PALETTE[2] if v < 250 else PALETTE[3] for v in vals]
    bars = ax.barh(names, vals, color=colors, height=0.6)
    for bar, val in zip(bars, vals):
        ax.text(bar.get_width() + 3, bar.get_y() + bar.get_height()/2,
                f"{val:+.0f}%", va="center", fontsize=10)
    ax.set_xlabel("Mean Per-Capita GDP Growth % across cluster districts (2014-2026)", fontsize=11)
    ax.set_title("Agrarian/Rural Cluster Rankings: Per-Capita GDP Growth 2014-2026\n"
                 "Vidarbha, Bundelkhand, KBK, Tribal Belt, Marathwada",
                 fontsize=12, fontweight="bold")
    ax.set_facecolor("#FAFAFA")
    ax.grid(True, axis="x", color="#E0E0E0")
    ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
    ax.annotate("Source: NASA VIIRS DNB / World Bank",
                xy=(0, -0.12), xycoords="axes fraction", fontsize=7.5, color="#777")
    fig.tight_layout()
    chart2 = str(OUTPUT_DIR / "rural_cluster_rankings.png")
    fig.savefig(chart2, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Chart -> {chart2}")

# Chart 3: Individual district charts for each cluster
for cluster_name, series_list in cluster_series.items():
    if not series_list:
        continue
    cluster_slug = cluster_name.split("(")[0].strip().lower().replace(" ", "_")
    cluster_dir = OUTPUT_DIR / cluster_slug
    cluster_dir.mkdir(exist_ok=True)
    for s in series_list:
        try:
            plot_city_report(s, save_dir=str(cluster_dir / s.city.lower().replace(" ", "_")))
        except Exception:
            pass
print(f"  Individual city charts saved to {OUTPUT_DIR}/")

# Export CSV
rows = []
for admin2, (s_u, s_r) in donut_pairs.items():
    for s, kind in [(s_u, "urban"), (s_r, "rural")]:
        for _, row in s.df.iterrows():
            rows.append({"district": admin2, "type": kind, "city": s.city,
                         "year": int(row["year"]),
                         "gdp_per_capita": round(row.get("gdp_per_capita", float("nan")), 2)})
for cluster_name, series_list in cluster_series.items():
    for s in series_list:
        for _, row in s.df.iterrows():
            rows.append({"district": s.city, "type": "rural_cluster",
                         "city": f"{cluster_name}: {s.city}",
                         "year": int(row["year"]),
                         "gdp_per_capita": round(row.get("gdp_per_capita", float("nan")), 2)})
csv_path = OUTPUT_DIR / "rural_analysis.csv"
pd.DataFrame(rows).to_csv(csv_path, index=False)

print(f"\n{'='*65}")
print(f"  Done. All outputs in: {OUTPUT_DIR.resolve()}/")
print(f"{'='*65}")
