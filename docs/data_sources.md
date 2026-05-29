# Data Sources

## Satellite Data (via Google Earth Engine)

### VIIRS DNB Monthly Composites
- **GEE Collection**: `NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG`
- **Band used**: `avg_rad` (mean radiance, nW/cm²/sr), `cf_cvg` (cloud-free obs count)
- **Coverage**: Global, 2012-01 to present
- **Resolution**: ~500m (resampled from 750m nadir)
- **Update frequency**: Monthly
- **Variant**: VCMSLCFG = stray-light corrected (preferred for tropical/high-latitude use)
- **Original source**: NOAA/NGDC https://ngdc.noaa.gov/eog/viirs/download_dnb_composites.html

### Administrative Boundaries
- **GEE Collection**: `FAO/GAUL/2015/level0` (country), `level1` (state), `level2` (district)
- **Source**: Food and Agriculture Organization Global Administrative Unit Layers (GAUL)
- **Year**: 2015 vintage (used for consistent boundary definitions)

### GHS-POP Population Grid
- **GEE Collection**: `JRC/GHSL/P2023A/GHS_POP`
- **Resolution**: 100m
- **Epochs**: 1975, 1980, 1985, 1990, 1995, 2000, 2005, 2010, 2015, 2020, 2025, 2030
- **Source**: JRC (Joint Research Centre, European Commission)
- **Data page**: https://ghsl.jrc.ec.europa.eu/ghs_pop2023.php
- **Citation**: Schiavina, M., Freire, S., Carioli, A., MacManus, K. (2023). GHS-POP R2023A - GHS population grid multitemporal (1975-2030). European Commission, Joint Research Centre (JRC). DOI: 10.2905/2FF68A52-5B5B-4A22-8F40-C41DA8332CFE

---

## Economic Data (via REST APIs)

### World Bank PPP Conversion Factors
- **Indicator**: `PA.NUS.PPP` — PPP conversion factor (GDP), LCU per international $
- **API endpoint**: `https://api.worldbank.org/v2/country/{code}/indicator/PA.NUS.PPP`
- **Coverage**: Most countries, annual, ~1990 to present
- **Caching**: Results cached locally in `~/.cache/nightlights_econ/ppp_cache.json`
- **Documentation**: https://datahelpdesk.worldbank.org/knowledgebase/articles/898599

---

## Reference Data (embedded in package)

### India LED Penetration (SLNP)
- **Source**: Ministry of Power, Government of India — SLNP Annual Progress Reports
- **Data**: Street light LED penetration rates by state, 2015–2025
- **SLNP portal**: https://slnp.gov.in
- **Key statistic**: 1.88 lakh LED luminaires installed in J&K as of 2022 (from MoP report)
- **File**: `src/nightlights_econ/lighting_tech.py` → `INDIA_LED_PENETRATION`

### India District Population (Census)
- **Source**: Census of India 2001, 2011 (Office of the Registrar General & Census Commissioner)
- **Coverage**: Key districts for validation (Pune, Bengaluru, Ayodhya, Srinagar, Leh, etc.)
- **Projections**: Interpolated/extrapolated using state-level growth rates
- **File**: `src/nightlights_econ/data/india_districts.py`

### Known Electrification Events
- **Leh, Ladakh (2017)**: 220kV Srinagar–Leh HVDC transmission line energised
  - Source: Power Grid Corporation of India press release, 2017
  - Effect: +138% radiance increase (Vaidya 2024 analysis)
- **Saubhagya Scheme (2017–2019)**: Near-universal household electrification in UP and J&K
  - Source: Ministry of Power, Saubhagya scheme reports
  - https://saubhagya.gov.in

---

## Academic References

| Citation | Relevance |
|----------|-----------|
| Henderson, V., Storeygard, A., Weil, D.N. (2012). "Measuring Economic Growth from Outer Space." *American Economic Review*, 102(2), 994-1028. | Foundational GDP-radiance elasticity (β = 0.88) |
| Patnaik, U., Shah, M., Tayal, A., Thomas, T. (2021). "But clouds got in my way." xKDR Working Paper 7. | Cloud-bias correction algorithm |
| Elvidge, C.D., et al. (2017). "VIIRS night-time lights." *International Journal of Remote Sensing*, 38(21), 5860-5879. | VIIRS spectral characteristics, LED vs sodium comparison |
| Vaidya, A. (2024). "Measuring economic activity in Indian cities using nighttime lights." Medium / personal analysis. | India-specific elasticities, Ayodhya/Srinagar/Leh case studies |
| Schiavina, M., et al. (2023). GHS-POP R2023A. European Commission JRC. | Population grid methodology |

---

## Notes on Data Access

- **Google Earth Engine** requires a free account at https://earthengine.google.com and authentication via `earthengine authenticate`. Academic/research use is free; commercial use requires a paid plan.
- **World Bank API** is public, no authentication required.
- **SLNP data** is embedded in the package as a static dict derived from public reports; no API call needed.
