"""
Example 1: Ayodhya deep dive.

Demonstrates the full pipeline for a single Indian city:
- Cloud-bias correction (monsoon months)
- LED spectral correction (SLNP rollout in UP)
- Electrification adjustment
- GDP proxy, per-capita, PPP-adjusted indices
- Event annotation (Bhoomi Pujan Aug 2020)
- All 4 single-city charts

Run:
    python examples/01_single_city.py

Requirements:
    - Google Earth Engine authenticated (earthengine authenticate)
    - GOOGLE_CLOUD_PROJECT env var set, or pass project_id below
"""

import os
from pathlib import Path

from nightlights_econ import (
    NighttimeLightsEngine,
    CityDefinition,
    LightingTechConfig,
)
from nightlights_econ.plotting import plot_city_report
from nightlights_econ.analysis import total_growth_pct, shock_analysis

OUTPUT_DIR = Path("./reports/ayodhya")

# -------------------------------------------------------------------
# 1. Define the city
# -------------------------------------------------------------------
ayodhya = CityDefinition(
    name="Ayodhya",
    country="India",
    admin1="Uttar Pradesh",
    admin2="Ayodhya",
    country_code="IND",
)

# -------------------------------------------------------------------
# 2. Configure LED + electrification correction for Uttar Pradesh
# -------------------------------------------------------------------
lta = LightingTechConfig(
    state="uttar pradesh",
    country_code="IND",
    apply_led_correction=True,
    apply_electrification_correction=True,
    apply_efficiency_dampening=True,
)

# -------------------------------------------------------------------
# 3. Initialize the engine
# -------------------------------------------------------------------
engine = NighttimeLightsEngine(
    project_id=os.environ.get("GOOGLE_CLOUD_PROJECT"),
    lighting_tech_config=lta,
    elasticity=0.95,  # India-specific calibration (Vaidya 2024)
)

# -------------------------------------------------------------------
# 4. Run analysis
# -------------------------------------------------------------------
print("Analyzing Ayodhya 2014–2026…")
series = engine.analyze(
    ayodhya,
    start_year=2014,
    end_year=2026,
    base_year=2014,
)

# -------------------------------------------------------------------
# 5. Print summary stats
# -------------------------------------------------------------------
print(f"\nCity: {series.city}")
print(f"Period: {series.start_year}–{series.end_year}")
print(f"Geometry area: {series.geometry_area_km2:.0f} km²")
print(f"GDP proxy growth (2014→2026): {total_growth_pct(series, 'gdp_proxy'):+.1f}%")
print(f"Per-capita growth:             {total_growth_pct(series, 'gdp_per_capita'):+.1f}%")
print(f"PPP-adj per-capita growth:     {total_growth_pct(series, 'gdp_ppp_per_capita'):+.1f}%")

# -------------------------------------------------------------------
# 6. Shock analysis: Bhoomi Pujan effect
# -------------------------------------------------------------------
print("\nShock analysis: post-Bhoomi Pujan (Aug 2020)…")
shock = shock_analysis(series, event_date="2020-08-05", window_months=18)
if "error" not in shock:
    print(f"  Pre-event mean GDP proxy:  {shock['pre_mean']:.1f}")
    print(f"  Post-event mean GDP proxy: {shock['post_mean']:.1f}")
    print(f"  Change: {shock['drop_pct']:+.1f}%")
    print(f"  Resilience score: {shock['resilience_score']:.0f}/100")

# -------------------------------------------------------------------
# 7. Generate all charts
# -------------------------------------------------------------------
events = [
    {"date": "2020-08-05", "label": "Bhoomi Pujan"},
    {"date": "2024-01-22", "label": "Temple Consecration"},
]

print(f"\nGenerating charts → {OUTPUT_DIR}")
figs = plot_city_report(series, save_dir=str(OUTPUT_DIR), events=events)
print(f"Saved {len(figs)} charts.")
