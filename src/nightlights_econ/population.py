"""Population extraction from GHS-POP via Google Earth Engine + interpolation."""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from .utils import interpolate_population

if TYPE_CHECKING:
    import ee

# JRC GHS-POP epoch years available in GEE
GHS_POP_COLLECTION = "JRC/GHSL/P2023A/GHS_POP"
GHS_POP_EPOCHS = [1975, 1980, 1985, 1990, 1995, 2000, 2005, 2010, 2015, 2020, 2025, 2030]


def extract_population_gee(
    geometry,
    target_years: list[int],
    scale: int = 1000,
) -> dict[int, float]:
    """Extract GHS-POP population counts for a geometry and interpolate to target years.

    Args:
        geometry: ee.Geometry defining the region.
        target_years: List of years to return population estimates for.
        scale: Pixel resolution in meters for the GEE reduce operation.

    Returns:
        Dict {year: population_count}.
    """
    try:
        import ee
    except ImportError:
        raise ImportError("earthengine-api is required. Run: pip install earthengine-api")

    collection = ee.ImageCollection(GHS_POP_COLLECTION)
    known: dict[int, float] = {}

    for epoch in GHS_POP_EPOCHS:
        try:
            img = collection.filter(ee.Filter.eq("system:index", str(epoch))).first()
            if img is None:
                img = collection.filter(
                    ee.Filter.eq("year", epoch)
                ).first()

            result = img.reduceRegion(
                reducer=ee.Reducer.sum(),
                geometry=geometry,
                scale=scale,
                maxPixels=1e9,
            ).getInfo()

            pop_val = result.get("population_count") or result.get("b1") or 0.0
            known[epoch] = float(pop_val)
        except Exception:
            continue

    if not known:
        raise RuntimeError("Could not extract any GHS-POP epochs for the given geometry.")

    return interpolate_population(known, target_years)


def get_population_series(
    city,
    target_years: list[int],
    geometry=None,
    scale: int = 1000,
) -> dict[int, float]:
    """Get population series for a CityDefinition.

    Uses city.population_series override if provided, otherwise fetches from GEE.

    Args:
        city: CityDefinition instance.
        target_years: Years to return estimates for.
        geometry: ee.Geometry (must be provided if not using override).
        scale: GEE reduce scale in meters.

    Returns:
        Dict {year: population}.
    """
    if city.population_series is not None:
        return interpolate_population(city.population_series, target_years)

    if geometry is None:
        raise ValueError(
            f"geometry must be provided to fetch GHS-POP for '{city.name}'"
        )

    return extract_population_gee(geometry, target_years, scale=scale)


def estimate_population_india_census(
    district: str,
    state: str,
    target_years: list[int],
) -> dict[int, float]:
    """Use known India Census 2011 data + growth rates to estimate population.

    Args:
        district: District name.
        state: State name.
        target_years: Years to return estimates for.

    Returns:
        Dict {year: population} or empty dict if district not in database.
    """
    from .data.india_districts import INDIA_DISTRICT_POPULATION

    key = f"{state.lower()}|{district.lower()}"
    if key not in INDIA_DISTRICT_POPULATION:
        return {}

    data = INDIA_DISTRICT_POPULATION[key]
    return interpolate_population(data, target_years)
