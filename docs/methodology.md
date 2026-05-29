# Methodology

## Overview

`nightlights-econ` estimates economic activity using satellite-detected nighttime radiance as a proxy for GDP. The pipeline has five correction layers, each addressing a specific bias.

---

## 1. Data: VIIRS DNB Monthly Composites

**Collection**: `NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG`

The Visible Infrared Imaging Radiometer Suite (VIIRS) Day/Night Band (DNB) measures radiance in the 500nm–900nm range with ~750m nadir resolution. The `VCMSLCFG` variant applies stray-light correction, which improves data quality at higher latitudes and is preferred for tropical regions.

Each monthly composite includes:
- `avg_rad`: Mean radiance (nW/cm²/sr) from cloud-free observations
- `cf_cvg`: Cloud-free observation count

**Radiance cap**: Values above 100 nW/cm²/sr are capped to exclude gas flares, volcanoes, and wildfires.

---

## 2. Cloud-Bias Correction (xKDR algorithm)

### Problem
During monsoon months (June–September), cloud cover reduces cloud-free satellite passes from ~12/month to 1–3. The monthly composite has fewer observations to average over, and the observations that do exist may be biased toward high-radiance (clear-sky) moments. Net effect: measured radiance is biased **-10% to -30%** below true levels.

### Algorithm
For each city/region time series:

1. Classify months as "good" (cf_obs ≥ 8) or "cloudy" (cf_obs < 8)
2. On good months, fit OLS: `radiance = α + β × cf_obs`
3. Compute `median_cf` = median of good-month cf_obs values
4. For each cloudy month `i`:
   - `predicted_at_actual = α + β × cf_obs[i]`
   - `predicted_at_median = α + β × median_cf`
   - `ratio = predicted_at_median / predicted_at_actual`
   - If `ratio > 1`: `corrected[i] = raw[i] × ratio` (upward only)
5. Fall back to seasonal median ratio if fewer than 3 good months exist

**Constraint**: Correction is strictly upward. Cloud bias is always downward; we never correct downward.

**Reference**: Patnaik, Shah, Tayal, Thomas (2021). "But clouds got in my way: Measuring Economic Activity Using Nighttime Lights." xKDR Working Paper 7.

---

## 3. Lighting Technology Adjustment (LTA)

### Problem: LED Spectral Shift
India's SLNP (Street Lighting National Programme) replaced sodium vapour street lights with white LEDs at scale — 1.88 lakh luminaires in J&K alone by 2022. The VIIRS DNB sensor's spectral response peaks at ~700nm where sodium's orange emission (589nm doublet) registers strongly. White LEDs have a broader, flatter spectrum that generates **~42–58% less VIIRS signal per watt** compared to sodium, despite equal or greater actual luminous output.

Net effect: a city undergoing LED replacement *appears to stagnate or decline* in nighttime lights even if its economy is growing.

### Signal Model
Let `p(t)` = fraction of street lights that are LED in year `t`. The aggregate VIIRS signal relative to a pure-sodium baseline:

```
apparent_signal(t) = [1 − p(t)] × 1.0 + p(t) × r_net
```

where `r_net = r_LED_viirs / r_LED_efficiency ≈ 0.55 / 1.30 ≈ 0.42`.

Upward correction factor:
```
led_factor(t) = 1 / apparent_signal(t)
```

### LED Penetration Data
State-level LED penetration rates are estimated from SLNP Annual Progress Reports (Ministry of Power, GoI), which publish installation counts by state. The `INDIA_LED_PENETRATION` dict in `lighting_tech.py` encodes these rates for major states. Unknown states fall back to a national default curve.

### Problem: Electrification Jumps
One-time radiance spikes occur when a region transitions from diesel/off-grid to grid power. These are infrastructure events, not GDP growth. Example: Leh (Ladakh) showed a +138% radiance increase in 2017 from the 220kV Srinagar–Leh transmission line — this appeared as extraordinary GDP growth but was mostly electrification.

The LTA module dampens known electrification events by reducing the radiance in the jump year and the following year by the estimated electrification fraction.

### Problem: Energy Efficiency Dampening
Tightening efficiency standards (BEE star ratings, LED replacement in commercial and industrial settings) mean the same economic activity uses fewer watts year-over-year. Post-2015, we apply a ~1.5%/year upward efficiency correction to account for this.

---

## 4. GDP Proxy Estimation (Henderson Elasticity)

### Model
The relationship between nighttime radiance and GDP follows a log-linear model (Henderson et al., 2012):

```
log(GDP) = α + β × log(radiance)
```

Rearranged as an index:
```
GDP_proxy(t) = 100 × (radiance(t) / radiance_base)^β
```

where `β = 0.88` is the Henderson elasticity (cross-country OLS estimate).

### India-specific calibration
Vaidya (2024) reports India-specific elasticities of 0.917–0.977 using district-level GDP data. These higher values reflect India's more radiance-intensive growth pattern (more services, less heavy industry). Pass `elasticity=0.95` to `NighttimeLightsEngine` for India-focused analysis.

---

## 5. Population Normalization

### GHS-POP Source
Population is extracted from the JRC Global Human Settlement Population grid (`JRC/GHSL/P2023A/GHS_POP`), available at 100m resolution. Epochs: 1975, 1980, 1985, 1990, 1995, 2000, 2005, 2010, 2015, 2020, 2025, 2030.

Annual estimates are produced by:
- Linear interpolation between available epochs
- Compound growth rate extrapolation beyond the last epoch

### Per-capita index
```
GDP_per_capita(t) = [GDP_proxy(t) / population(t)] / [GDP_proxy_base / population_base] × 100
```

This ensures the base year = 100 for both the total and per-capita indices.

---

## 6. PPP Adjustment

The PPP conversion factor `PPP(t)` (local currency units per international dollar) is fetched from the World Bank API (indicator `PA.NUS.PPP`). All factors are normalized to the base year:

```
PPP_relative(t) = PPP(t) / PPP(base)
GDP_PPP_per_capita(t) = GDP_per_capita(t) / PPP_relative(t)
```

Since `PPP_relative(base) = 1`, the PPP-adjusted index also starts at 100. Divergence between the nominal and PPP-adjusted indices captures inflation and currency depreciation effects.

---

## 7. Shock Analysis

For an event at time `t_0` with window `W` months:

- **Pre-event window**: `[t_0 − W, t_0)`
- **Post-event window**: `[t_0, t_0 + W)`
- **Drop**: `(mean_post − mean_pre) / mean_pre × 100%`
- **Recovery months**: First month in the post-event window where the series returns to or exceeds the pre-event level
- **Resilience score**: `100 − severity_penalty − recovery_penalty`, where `severity_penalty = min(|drop%| × 2, 60)` and `recovery_penalty` is based on recovery months (40 if never recovered in window)

---

## Known Limitations

1. **VIIRS measures outdoor lighting**, not total economic activity. Service-sector growth (offices, restaurants) drives radiance; heavy manufacturing may not. The elasticity partially accounts for this.

2. **Gas flares and wildfires** are capped at 100 nW/cm²/sr but large events near urban areas can still bias results.

3. **Informal economy** operates in daylight and may not generate proportional lighting. India's informal sector (~50% of GDP) likely makes the Henderson elasticity an underestimate.

4. **LED penetration data** for non-Indian regions uses a generic global S-curve. For accurate LTA in other countries, supply `custom_led_penetration` in `LightingTechConfig`.

5. **GHS-POP** has 5-year epochs. Cities with unusual migration patterns (Leh: influx of military and tourism; Ayodhya: religious pilgrimage) may require Census overrides via `CityDefinition.population_series`.

6. **Monthly composites** lose within-month variation. Sudden events (earthquake, flood) may take 2–3 months to register clearly in the composite.
