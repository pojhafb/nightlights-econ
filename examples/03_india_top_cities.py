"""
Example 3: India top cities batch analysis and rankings.

Demonstrates:
- Batch analysis of major Indian cities
- State-specific LED correction configs
- Top/bottom rankings chart
- Correlation matrix across cities

Run:
    python examples/03_india_top_cities.py
"""

import os
from pathlib import Path

import pandas as pd

from nightlights_econ import (
    NighttimeLightsEngine,
    CityDefinition,
    LightingTechConfig,
)
from nightlights_econ.rankings import rank_cities
from nightlights_econ.plotting import plot_rankings, plot_city_comparison
from nightlights_econ.analysis import compute_correlation_matrix, total_growth_pct

OUTPUT_DIR = Path("./reports/india_rankings")

# -------------------------------------------------------------------
# 1. Define cities across India
# -------------------------------------------------------------------
CITIES = [
    CityDefinition("Pune",       country="India", admin1="Maharashtra",   admin2="Pune"),
    CityDefinition("Mumbai",     country="India", admin1="Maharashtra",   admin2="Mumbai City"),
    CityDefinition("Bangalore",  country="India", admin1="Karnataka",     admin2="Bangalore Urban"),
    CityDefinition("Chennai",    country="India", admin1="Tamil Nadu",    admin2="Chennai"),
    CityDefinition("Hyderabad",  country="India", admin1="Telangana",     admin2="Hyderabad"),
    CityDefinition("Ahmedabad",  country="India", admin1="Gujarat",       admin2="Ahmedabad"),
    CityDefinition("Jaipur",     country="India", admin1="Rajasthan",     admin2="Jaipur"),
    CityDefinition("Lucknow",    country="India", admin1="Uttar Pradesh", admin2="Lucknow"),
    CityDefinition("Srinagar",   country="India", admin1="Jammu and Kashmir", admin2="Srinagar"),
    CityDefinition("Ayodhya",    country="India", admin1="Uttar Pradesh", admin2="Ayodhya"),
]

# -------------------------------------------------------------------
# 2. Engine — generic India LED config (state-specific correction
#    is automatically resolved per city's admin1)
# -------------------------------------------------------------------
lta = LightingTechConfig(
    country_code="IND",
    apply_led_correction=True,
    apply_electrification_correction=True,
    apply_efficiency_dampening=True,
)

engine = NighttimeLightsEngine(
    project_id=os.environ.get("GOOGLE_CLOUD_PROJECT"),
    lighting_tech_config=lta,
    elasticity=0.95,
)

# -------------------------------------------------------------------
# 3. Batch analysis
# -------------------------------------------------------------------
print(f"Analyzing {len(CITIES)} Indian cities 2014–2026…")
series_list = engine.analyze_many(CITIES, start_year=2014, end_year=2026)

# -------------------------------------------------------------------
# 4. Rankings
# -------------------------------------------------------------------
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

ranking_pc = rank_cities(series_list, metric="per_capita_growth", top_n=5, bottom_n=3)
ranking_total = rank_cities(series_list, metric="total_growth", top_n=5, bottom_n=3)

print("\n--- Per-Capita Growth Ranking (Top 5 / Bottom 3) ---")
print(ranking_pc[["city", "per_capita_growth", "rank"]].to_string(index=False))

print("\n--- Total GDP Proxy Growth Ranking ---")
print(ranking_total[["city", "total_growth", "rank"]].to_string(index=False))

# -------------------------------------------------------------------
# 5. Charts
# -------------------------------------------------------------------
fig_pc = plot_rankings(
    ranking_pc,
    metric="per_capita_growth",
    title="India Cities: Per-Capita GDP Growth (VIIRS + LED Correction)",
    save_path=str(OUTPUT_DIR / "india_rankings_per_capita.png"),
)

fig_total = plot_rankings(
    ranking_total,
    metric="total_growth",
    title="India Cities: Total GDP Proxy Growth (VIIRS + LED Correction)",
    save_path=str(OUTPUT_DIR / "india_rankings_total.png"),
)

fig_comparison = plot_city_comparison(
    series_list[:6],  # top 6 for readable chart
    save_path=str(OUTPUT_DIR / "india_top6_comparison.png"),
)

# -------------------------------------------------------------------
# 6. Correlation matrix
# -------------------------------------------------------------------
corr = compute_correlation_matrix(series_list, metric="gdp_per_capita")
print("\n--- Per-Capita GDP Correlation Matrix ---")
print(corr.round(2).to_string())

corr.to_csv(OUTPUT_DIR / "india_correlation_matrix.csv")
print(f"\nAll charts and CSV saved to {OUTPUT_DIR}/")
