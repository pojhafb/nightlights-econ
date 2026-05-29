"""World Bank PPP conversion factor fetching with local JSON cache."""

from __future__ import annotations

import requests

from .utils import load_json_cache, save_json_cache

WORLD_BANK_INDICATOR = "PA.NUS.PPP"
CACHE_FILE = "ppp_cache.json"

# Hardcoded fallback values (INR per international $) for key countries
PPP_FALLBACKS: dict[str, dict[int, float]] = {
    "IND": {
        2014: 18.17, 2015: 18.69, 2016: 19.12, 2017: 19.58, 2018: 20.22,
        2019: 21.01, 2020: 21.87, 2021: 22.40, 2022: 23.19, 2023: 24.02,
        2024: 24.85, 2025: 25.70,
    },
    "UKR": {
        2014: 8.14, 2015: 9.82, 2016: 11.22, 2017: 11.74, 2018: 12.61,
        2019: 13.91, 2020: 15.39, 2021: 16.03, 2022: 17.27, 2023: 19.04,
        2024: 20.50, 2025: 22.10,
    },
    "KEN": {
        2014: 43.5, 2015: 44.8, 2016: 46.2, 2017: 47.8, 2018: 49.1,
        2019: 51.0, 2020: 52.4, 2021: 54.1, 2022: 56.3, 2023: 58.8,
        2024: 61.2, 2025: 63.7,
    },
}


def fetch_ppp_factors(
    country_code: str,
    start_year: int,
    end_year: int,
    force_refresh: bool = False,
) -> dict[int, float]:
    """Fetch PPP conversion factors from World Bank API.

    Results are cached locally in ~/.cache/nightlights_econ/ppp_cache.json.

    Args:
        country_code: ISO 3166-1 alpha-3 code (e.g., "IND").
        start_year: First year to retrieve.
        end_year: Last year to retrieve.
        force_refresh: If True, bypass local cache and re-fetch.

    Returns:
        Dict {year: ppp_factor} for available years.
    """
    cache = load_json_cache(CACHE_FILE)
    cache_key = country_code.upper()

    if not force_refresh and cache_key in cache:
        cached = {int(k): float(v) for k, v in cache[cache_key].items()}
        needed = set(range(start_year, end_year + 1))
        cached_years = set(cached.keys())
        if needed.issubset(cached_years):
            return {yr: cached[yr] for yr in range(start_year, end_year + 1) if yr in cached}

    try:
        fetched = _fetch_from_world_bank(country_code, start_year, end_year)
        if fetched:
            existing = cache.get(cache_key, {})
            existing.update({str(k): v for k, v in fetched.items()})
            cache[cache_key] = existing
            save_json_cache(CACHE_FILE, cache)
            return fetched
    except Exception:
        pass

    return _get_fallback(country_code, start_year, end_year)


def _fetch_from_world_bank(
    country_code: str,
    start_year: int,
    end_year: int,
) -> dict[int, float]:
    """Call the World Bank API for PPP data.

    Returns:
        Dict {year: ppp_factor}.
    """
    # Convert alpha-3 to alpha-2 for World Bank API
    from .data.country_codes import ALPHA3_TO_ALPHA2
    alpha2 = ALPHA3_TO_ALPHA2.get(country_code.upper(), country_code[:2].upper())

    url = (
        f"https://api.worldbank.org/v2/country/{alpha2}/indicator/{WORLD_BANK_INDICATOR}"
        f"?format=json&date={start_year}:{end_year}&per_page=100"
    )
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()

    data = resp.json()
    if len(data) < 2 or not data[1]:
        return {}

    result = {}
    for entry in data[1]:
        if entry.get("value") is not None:
            result[int(entry["date"])] = float(entry["value"])
    return result


def _get_fallback(
    country_code: str,
    start_year: int,
    end_year: int,
) -> dict[int, float]:
    """Return hardcoded fallback PPP values, interpolating missing years."""
    from .utils import interpolate_population

    code = country_code.upper()
    known = PPP_FALLBACKS.get(code, {})
    if not known:
        # Generic neutral factor (1.0 = no PPP adjustment)
        return {yr: 1.0 for yr in range(start_year, end_year + 1)}

    return interpolate_population(known, list(range(start_year, end_year + 1)))


def relative_ppp_adjustment(
    ppp_factors: dict[int, float],
    base_year: int,
) -> dict[int, float]:
    """Normalize PPP factors relative to base year (base year = 1.0).

    Args:
        ppp_factors: Dict {year: ppp_factor}.
        base_year: Year to use as the reference (set to 1.0).

    Returns:
        Dict {year: relative_factor}.
    """
    base = ppp_factors.get(base_year, 1.0)
    if base == 0:
        return {yr: 1.0 for yr in ppp_factors}
    return {yr: v / base for yr, v in ppp_factors.items()}
