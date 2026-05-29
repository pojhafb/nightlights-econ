"""
Example 4: International cities — Kyiv (war impact), Nairobi (Africa growth).

Demonstrates:
- Non-India usage with point + radius geometry
- Generic global LED correction curve
- Kyiv: war shock analysis (Feb 2022 invasion)
- Nairobi: sustained growth narrative
- Multi-country comparison

Run:
    python examples/04_international.py
"""

import os
from pathlib import Path

from nightlights_econ import (
    NighttimeLightsEngine,
    CityDefinition,
    LightingTechConfig,
)
from nightlights_econ.analysis import shock_analysis, total_growth_pct
from nightlights_econ.plotting import (
    plot_city_report,
    plot_shock_resilience,
    plot_city_comparison,
)

OUTPUT_DIR = Path("./reports/international")

# -------------------------------------------------------------------
# 1. Define cities via lat/lon + radius
# -------------------------------------------------------------------
kyiv = CityDefinition(
    name="Kyiv",
    lat=50.4501,
    lon=30.5234,
    radius_km=25,
    country_code="UKR",
    country="Ukraine",
)

nairobi = CityDefinition(
    name="Nairobi",
    lat=-1.2921,
    lon=36.8219,
    radius_km=20,
    country_code="KEN",
    country="Kenya",
)

lagos = CityDefinition(
    name="Lagos",
    lat=6.5244,
    lon=3.3792,
    radius_km=30,
    country_code="NGA",
    country="Nigeria",
)

# -------------------------------------------------------------------
# 2. Engine with generic global LED correction
# -------------------------------------------------------------------
lta_global = LightingTechConfig(
    country_code="UKR",              # will auto-adapt per city in analyze_many
    apply_led_correction=True,
    apply_electrification_correction=False,  # no known events for these cities
    apply_efficiency_dampening=True,
)

engine = NighttimeLightsEngine(
    project_id=os.environ.get("GOOGLE_CLOUD_PROJECT"),
    lighting_tech_config=lta_global,
)

# -------------------------------------------------------------------
# 3. Analyse
# -------------------------------------------------------------------
print("Analyzing Kyiv (2019–2026)…")
kyiv_series = engine.analyze(kyiv, start_year=2019, end_year=2026, base_year=2019)

print("Analyzing Nairobi (2014–2026)…")
nairobi_series = engine.analyze(nairobi, start_year=2014, end_year=2026)

print("Analyzing Lagos (2014–2026)…")
lagos_series = engine.analyze(lagos, start_year=2014, end_year=2026)

# -------------------------------------------------------------------
# 4. Kyiv war shock analysis
# -------------------------------------------------------------------
print("\nKyiv — war shock analysis (2022-02-24)…")
kyiv_shock = shock_analysis(kyiv_series, event_date="2022-02-24", window_months=18)
if "error" not in kyiv_shock:
    kyiv_shock["city"] = "Kyiv"
    print(f"  Radiance drop: {kyiv_shock['drop_pct']:+.1f}%")
    print(f"  Resilience: {kyiv_shock['resilience_score']:.0f}/100")
    if kyiv_shock["recovery_months"]:
        print(f"  Recovery: {kyiv_shock['recovery_months']} months")
    else:
        print("  Recovery: not observed in 18-month window")

# -------------------------------------------------------------------
# 5. Comparative stats
# -------------------------------------------------------------------
print("\n--- Growth Comparison ---")
for s in [kyiv_series, nairobi_series, lagos_series]:
    print(
        f"  {s.city:10s}  GDP proxy: {total_growth_pct(s, 'gdp_proxy'):+6.1f}%  "
        f"Per-capita: {total_growth_pct(s, 'gdp_per_capita'):+6.1f}%"
    )

# -------------------------------------------------------------------
# 6. Charts
# -------------------------------------------------------------------
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

plot_city_report(
    kyiv_series, save_dir=str(OUTPUT_DIR / "kyiv"),
    events=[{"date": "2022-02-24", "label": "Russian Invasion"}],
)

plot_city_report(nairobi_series, save_dir=str(OUTPUT_DIR / "nairobi"))
plot_city_report(lagos_series, save_dir=str(OUTPUT_DIR / "lagos"))

if "error" not in kyiv_shock:
    plot_shock_resilience(
        [kyiv_shock],
        event_name="Russia–Ukraine War (Feb 2022)",
        save_path=str(OUTPUT_DIR / "kyiv_war_shock.png"),
    )

fig_comparison = plot_city_comparison(
    [kyiv_series, nairobi_series, lagos_series],
    save_path=str(OUTPUT_DIR / "international_comparison.png"),
)

print(f"\nAll charts saved to {OUTPUT_DIR}/")
