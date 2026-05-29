"""nightlights-econ: Measure real economic growth for any city using NASA satellite nighttime lights."""

from .core import CityDefinition, RadianceSeries
from .engine import NighttimeLightsEngine
from .cloud_correction import correct_cloud_bias, correction_stats
from .gdp_proxy import compute_gdp_proxy, compute_gdp_per_capita, compute_ppp_adjusted, compute_all_metrics
from .analysis import shock_analysis, growth_decomposition, compare_cities, total_growth_pct
from .ppp import fetch_ppp_factors
from .population import get_population_series
from .lighting_tech import (
    LightingTechConfig,
    apply_lighting_tech_adjustment,
    get_led_penetration,
    lta_correction_summary,
)
from .cache import (
    geometry_key,
    get_cached,
    save_to_cache,
    cache_info,
    invalidate,
    invalidate_all,
)
from .extractor import (
    extract_viirs_cached,
    extract_for_district,
    extract_for_point,
)

__version__ = "0.1.0"
__all__ = [
    "geometry_key", "get_cached", "save_to_cache", "cache_info",
    "invalidate", "invalidate_all",
    "extract_viirs_cached", "extract_for_district", "extract_for_point",
    "CityDefinition",
    "RadianceSeries",
    "NighttimeLightsEngine",
    "correct_cloud_bias",
    "correction_stats",
    "compute_gdp_proxy",
    "compute_gdp_per_capita",
    "compute_ppp_adjusted",
    "compute_all_metrics",
    "shock_analysis",
    "growth_decomposition",
    "compare_cities",
    "total_growth_pct",
    "fetch_ppp_factors",
    "get_population_series",
    "LightingTechConfig",
    "apply_lighting_tech_adjustment",
    "get_led_penetration",
    "lta_correction_summary",
]
