"""
Example 5: Custom GeoJSON boundary input.

Use cases:
- Special economic zones (not matching admin boundaries)
- Port areas, industrial corridors, metropolitan regions
- Cross-border regions

Demonstrates:
- GeoJSON geometry input to CityDefinition
- Delhi NCR (custom merged boundary)
- Custom population override (Census data)
- Custom LED penetration override

Run:
    python examples/05_custom_boundary.py
"""

import json
import os
from pathlib import Path

from nightlights_econ import (
    NighttimeLightsEngine,
    CityDefinition,
    LightingTechConfig,
)
from nightlights_econ.plotting import plot_city_report
from nightlights_econ.analysis import total_growth_pct

OUTPUT_DIR = Path("./reports/custom_boundary")

# -------------------------------------------------------------------
# 1. Define a custom GeoJSON boundary (Delhi NCR approximate)
# -------------------------------------------------------------------
# This is a simplified bounding polygon — replace with your actual GeoJSON.
# You can load from a file: json.load(open("my_region.geojson"))
delhi_ncr_geojson = {
    "type": "Polygon",
    "coordinates": [[
        [76.84, 28.40],
        [77.84, 28.40],
        [77.84, 29.00],
        [76.84, 29.00],
        [76.84, 28.40],
    ]]
}

delhi_ncr = CityDefinition(
    name="Delhi NCR",
    geometry=delhi_ncr_geojson,
    country_code="IND",
    # Override population with Census + NCR Planning Board estimates
    population_series={
        2001: 21_500_000,
        2011: 26_500_000,
        2021: 32_000_000,
        2026: 35_000_000,
    },
)

# -------------------------------------------------------------------
# 2. Custom LED penetration (Delhi NCR — aggressive SLNP adoption)
# -------------------------------------------------------------------
delhi_led_penetration = {
    2014: 0.02, 2015: 0.08, 2016: 0.20, 2017: 0.38,
    2018: 0.58, 2019: 0.73, 2020: 0.83, 2021: 0.89,
    2022: 0.93, 2023: 0.96, 2024: 0.97, 2025: 0.98,
}

lta = LightingTechConfig(
    country_code="IND",
    apply_led_correction=True,
    apply_electrification_correction=False,
    apply_efficiency_dampening=True,
    custom_led_penetration=delhi_led_penetration,
)

# -------------------------------------------------------------------
# 3. Engine
# -------------------------------------------------------------------
engine = NighttimeLightsEngine(
    project_id=os.environ.get("GOOGLE_CLOUD_PROJECT"),
    lighting_tech_config=lta,
    elasticity=0.95,
    scale=500,
)

# -------------------------------------------------------------------
# 4. Analyse
# -------------------------------------------------------------------
print("Analyzing Delhi NCR 2014–2026 with custom GeoJSON boundary…")
series = engine.analyze(delhi_ncr, start_year=2014, end_year=2026)

print(f"\nCity: {series.city}")
print(f"Area: {series.geometry_area_km2:.0f} km²")
print(f"GDP proxy growth: {total_growth_pct(series, 'gdp_proxy'):+.1f}%")
print(f"Per-capita growth: {total_growth_pct(series, 'gdp_per_capita'):+.1f}%")

# -------------------------------------------------------------------
# 5. Charts
# -------------------------------------------------------------------
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
plot_city_report(series, save_dir=str(OUTPUT_DIR))
print(f"\nCharts saved to {OUTPUT_DIR}/")

# -------------------------------------------------------------------
# 6. Compare: what would analysis look like WITHOUT LED correction?
# -------------------------------------------------------------------
print("\nComparing: with LTA vs without LTA…")
engine_no_lta = NighttimeLightsEngine(
    project_id=os.environ.get("GOOGLE_CLOUD_PROJECT"),
    elasticity=0.95,
)
series_no_lta = engine_no_lta.analyze(delhi_ncr, start_year=2014, end_year=2026)
series_no_lta.city = "Delhi NCR (no LTA)"

print(f"  With LTA:    per-capita growth = {total_growth_pct(series, 'gdp_per_capita'):+.1f}%")
print(f"  Without LTA: per-capita growth = {total_growth_pct(series_no_lta, 'gdp_per_capita'):+.1f}%")
print("  Difference shows the LED understatement bias that LTA corrects for.")
