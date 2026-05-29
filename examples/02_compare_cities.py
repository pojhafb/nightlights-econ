"""
Example 2: Srinagar vs Leh vs Manali — Kashmir valley comparison.

Demonstrates:
- Multi-city comparison with different LTA configs (J&K vs Himachal)
- Shock analysis (Pahalgam attack, Apr 2025) across all three cities
- City comparison dashboard chart
- Shock resilience comparison chart

Run:
    python examples/02_compare_cities.py
"""

import os
from pathlib import Path

from nightlights_econ import (
    NighttimeLightsEngine,
    CityDefinition,
    LightingTechConfig,
)
from nightlights_econ.analysis import shock_analysis, total_growth_pct
from nightlights_econ.plotting import plot_city_comparison, plot_shock_resilience, plot_city_report
from nightlights_econ.rankings import rank_cities

OUTPUT_DIR = Path("./reports/kashmir")

# -------------------------------------------------------------------
# 1. Define cities
# -------------------------------------------------------------------
srinagar = CityDefinition(
    name="Srinagar",
    country="India",
    admin1="Jammu and Kashmir",
    admin2="Srinagar",
    country_code="IND",
)

leh = CityDefinition(
    name="Leh",
    country="India",
    admin1="Ladakh",
    admin2="Leh",
    country_code="IND",
)

manali = CityDefinition(
    name="Manali",
    country="India",
    admin1="Himachal Pradesh",
    admin2="Kullu",         # Manali is in Kullu district
    country_code="IND",
)

# -------------------------------------------------------------------
# 2. Engine with J&K LED config (LED penetration data for JK)
# -------------------------------------------------------------------
lta_jk = LightingTechConfig(
    state="jammu and kashmir",
    apply_electrification_correction=True,  # Saubhagya 2019 jump
)

engine = NighttimeLightsEngine(
    project_id=os.environ.get("GOOGLE_CLOUD_PROJECT"),
    lighting_tech_config=lta_jk,
    elasticity=0.95,
)

# -------------------------------------------------------------------
# 3. Analyse all three cities
# -------------------------------------------------------------------
print("Analyzing Srinagar, Leh, and Manali 2014–2026…")
cities = [srinagar, leh, manali]
series_list = engine.analyze_many(cities, start_year=2014, end_year=2026)

# -------------------------------------------------------------------
# 4. Print comparative stats
# -------------------------------------------------------------------
print("\n--- Comparative Growth Summary ---")
for s in series_list:
    print(
        f"  {s.city:12s}  GDP proxy: {total_growth_pct(s, 'gdp_proxy'):+6.1f}%  "
        f"Per-capita: {total_growth_pct(s, 'gdp_per_capita'):+6.1f}%"
    )

# -------------------------------------------------------------------
# 5. Rankings
# -------------------------------------------------------------------
ranking = rank_cities(series_list, metric="per_capita_growth", top_n=3, bottom_n=1)
print("\n--- Per-Capita Growth Ranking ---")
print(ranking[["city", "per_capita_growth", "rank"]].to_string(index=False))

# -------------------------------------------------------------------
# 6. Shock analysis: Pahalgam attack (Apr 2025)
# -------------------------------------------------------------------
print("\nShock analysis: Pahalgam attack (2025-04-22)…")
shock_results = []
for s in series_list:
    result = shock_analysis(s, event_date="2025-04-22", window_months=6)
    if "error" not in result:
        result["city"] = s.city
        shock_results.append(result)
        print(f"  {s.city:12s} → drop: {result['drop_pct']:+.1f}%  resilience: {result['resilience_score']:.0f}/100")

# -------------------------------------------------------------------
# 7. Generate charts
# -------------------------------------------------------------------
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

print(f"\nGenerating comparison dashboard → {OUTPUT_DIR}")
fig_comparison = plot_city_comparison(
    series_list,
    save_path=str(OUTPUT_DIR / "kashmir_comparison_dashboard.png"),
)

if shock_results:
    fig_shock = plot_shock_resilience(
        shock_results,
        event_name="Pahalgam Attack (Apr 2025)",
        save_path=str(OUTPUT_DIR / "kashmir_shock_resilience.png"),
    )
    print("Saved shock resilience chart.")

# Individual city reports
for s in series_list:
    events = [{"date": "2025-04-22", "label": "Pahalgam Attack"}]
    plot_city_report(s, save_dir=str(OUTPUT_DIR / s.city.lower()), events=events)

print("Done.")
