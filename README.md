# nightlights-econ

**Measure real economic growth for any city using NASA satellite nighttime lights.**

GDP/capita · PPP-adjusted · Population-normalized · Cloud-corrected · LED-bias-corrected

---

Every night between 1:30–2:30 AM, NASA's Suomi NPP satellite photographs how bright every 500m patch of ground is. This brightness (nighttime radiance) correlates with real GDP at **r = 0.88** (Henderson et al., 2012). `nightlights-econ` productionizes this into a Python library that turns raw satellite data into publication-quality economic analysis for any city on Earth.

Inspired by [Abhijit Vaidya's analysis](https://medium.com/@abhijit.vaidya) of Indian cities using the xKDR Forum's methodology.

---

## What it does

```
Satellite VIIRS DNB
        ↓
  Cloud Correction (xKDR algorithm — critical for Indian monsoon)
        ↓
  LED Spectral Correction (India's SLNP LED rollout dims the signal)
        ↓
  Population normalization (GHS-POP satellite grids)
        ↓
  PPP adjustment (World Bank API)
        ↓
  GDP proxy index · per-capita · PPP-adjusted
        ↓
  7 publication-quality charts · shock analysis · city rankings
```

---

## Quick start

```bash
pip install nightlights-econ
earthengine authenticate   # one-time GEE authentication
```

### Python API

```python
from nightlights_econ import NighttimeLightsEngine, CityDefinition, LightingTechConfig

engine = NighttimeLightsEngine(
    project_id="your-gcp-project",
    lighting_tech_config=LightingTechConfig(state="uttar pradesh"),  # LED correction
)

ayodhya = CityDefinition(
    name="Ayodhya",
    country="India",
    admin1="Uttar Pradesh",
    admin2="Ayodhya",
    country_code="IND",
)

series = engine.analyze(ayodhya, start_year=2014, end_year=2026)

from nightlights_econ.plotting import plot_city_report
plot_city_report(series, save_dir="./reports/ayodhya/", events=[
    {"date": "2020-08-05", "label": "Bhoomi Pujan"},
])
```

### CLI

```bash
# Single city
nightlights analyze \
  --city "Ayodhya" --country India --state "Uttar Pradesh" --district Ayodhya \
  --start 2014 --end 2026 \
  --event-date 2020-08-05 --event-name "Bhoomi Pujan" \
  --output ./reports/ayodhya/

# Compare cities
nightlights compare \
  --cities "Srinagar,Leh,Manali" --country India \
  --start 2014 --end 2026 --output ./reports/kashmir/

# Shock analysis
nightlights shock \
  --city "Srinagar" --country India \
  --event-date 2025-04-22 --event-name "Pahalgam Attack" \
  --output ./reports/

# Country rankings
nightlights rank \
  --country India --states "Uttar Pradesh,Maharashtra,Karnataka" \
  --top 5 --bottom 5 --metric per_capita_growth

# By coordinates (international)
nightlights analyze \
  --name "Kyiv" --lat 50.45 --lon 30.52 --radius 20 --country-code UKR \
  --start 2019 --end 2026 --output ./reports/kyiv/

# Quick stats
nightlights quick --city "Pune" --country India
```

---

## Charts generated

| Chart | Description |
|-------|-------------|
| **GDP + Population** | Dual-axis: GDP proxy index vs population, monsoon shading, event annotations |
| **Per-Capita GDP** | Single-line index with ±1σ confidence band + YoY growth bars |
| **PPP-Adjusted** | Nominal vs PPP-adjusted per-capita — divergence shows inflation/FX effect |
| **Raw Radiance** | Raw vs cloud-corrected radiance + cloud-free observation count subplot |
| **City Comparison** | 2×2 dashboard: radiance growth, per-capita growth, ranked bar charts |
| **Rankings** | Traffic-light horizontal bars — top/bottom cities with population annotation |
| **Shock Resilience** | Pre/post shock trajectories across cities with resilience scores |

---

## Key corrections applied

### 1. Cloud-bias correction (xKDR algorithm)
During India's monsoon (June–September), cloud cover reduces cloud-free satellite observations from ~12/month to 1–3. Measured radiance is biased **-10% to -30%**. The algorithm:
- Fits a linear model: `radiance = f(cf_obs)` on clear months (cf_obs ≥ 8)
- Predicts what radiance *would have been* at median clear-sky coverage
- Applies an upward ratio correction to cloudy months only

Reference: Patnaik, Shah, Tayal, Thomas (2021) "But clouds got in my way" — xKDR WP7.

### 2. LED spectral correction (new)
India's SLNP (Street Lighting National Programme) replaced millions of sodium vapour lamps with white LEDs. **White LEDs appear ~42% as bright to VIIRS per watt** vs sodium, because VIIRS peaks in the orange band where sodium glows strongly. An LED replacement makes a growing city *appear to stagnate or dim* from space.

The correction:
- Uses SLNP Annual Reports to model LED penetration by state and year
- Computes: `apparent_signal = 1 - p × (1 - LED_net_viirs_ratio)` where `p` = LED fraction
- Applies upward factor `1 / apparent_signal` to each year

Effects captured:
- **LED spectral shift** — white LED vs sodium VIIRS sensitivity (ratio ≈ 0.55)
- **LED efficiency gain** — LEDs produce more lumens/watt (ratio ≈ 1.30), so same wattage → less VIIRS signal
- **Electrification jumps** — one-time spikes dampened (e.g., Leh 2017 +138% from 220kV line)
- **Efficiency standards** — gradual improvement in lumens/watt over time (+1.5%/yr post-2015)

### 3. Population normalization (GHS-POP)
Uses JRC Global Human Settlement Population grids (1km resolution). Epochs at 5-year intervals are linearly interpolated for annual estimates. Allows Census 2011 data injection for Indian districts.

### 4. PPP adjustment (World Bank)
Fetches `PA.NUS.PPP` from the World Bank API, cached locally. Normalized relative to base year so all indices start at 100.

---

## Henderson elasticity

The GDP proxy formula:
```
GDP_proxy(t) = 100 × (radiance(t) / radiance_base)^elasticity
```

Default elasticity: **0.88** (Henderson et al., 2012 global estimate).

India-specific values from Vaidya's work: 0.917–0.977 (can be passed to `NighttimeLightsEngine(elasticity=0.95)`).

---

## Installation

```bash
# From PyPI (when published)
pip install nightlights-econ

# From source
git clone https://github.com/YOUR_USERNAME/nightlights-econ
cd nightlights-econ
pip install -e ".[dev]"
```

### Google Earth Engine setup

```bash
pip install earthengine-api
earthengine authenticate
```

Or with a service account:
```python
engine = NighttimeLightsEngine(
    service_account="sa@project.iam.gserviceaccount.com",
    credentials_file="/path/to/key.json",
)
```

---

## Running tests

```bash
pytest tests/ -v
```

All tests run without GEE authentication — all satellite calls are mocked.

---

## Data sources

| Data | Source | Access |
|------|--------|--------|
| VIIRS DNB monthly | `NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG` | Google Earth Engine |
| Administrative boundaries | FAO GAUL 2015 | Google Earth Engine |
| Population | JRC GHS-POP P2023A | Google Earth Engine |
| PPP factors | World Bank `PA.NUS.PPP` | REST API |
| LED penetration (India) | SLNP Annual Progress Reports | Embedded in package |

See [docs/data_sources.md](docs/data_sources.md) for full details and URLs.

---

## Methodology

See [docs/methodology.md](docs/methodology.md) for the complete mathematical derivation, calibration notes, and known limitations.

---

## License

MIT — see [LICENSE](LICENSE).

---

## References

- Henderson, Vernon, Adam Storeygard, and David N. Weil. "Measuring Economic Growth from Outer Space." *American Economic Review* 102(2), 2012.
- Patnaik, Shah, Tayal, Thomas. "But clouds got in my way." xKDR Working Paper 7, 2021.
- Elvidge, C.D. et al. "VIIRS Night-time Lights." *International Journal of Remote Sensing*, 2017.
- India MoP. SLNP Annual Progress Reports, 2015–2024.
