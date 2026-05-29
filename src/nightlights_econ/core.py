"""Core data classes for the nightlights-econ toolkit."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Any

import pandas as pd


@dataclass
class CityDefinition:
    """Defines a city or region for analysis.

    Args:
        name: Human-readable city/region name.
        country: Country name (e.g., "India").
        admin1: State or province name.
        admin2: District name.
        geometry: ee.Geometry or GeoJSON dict defining the boundary.
        lat: Latitude for point+radius mode.
        lon: Longitude for point+radius mode.
        radius_km: Radius in km for point+radius mode.
        population_series: Optional dict {year: population} to override GHS-POP.
        country_code: ISO 3166-1 alpha-3 country code (default "IND").
    """

    name: str
    country: Optional[str] = None
    admin1: Optional[str] = None
    admin2: Optional[str] = None
    geometry: Optional[Any] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    radius_km: Optional[float] = None
    population_series: Optional[dict[int, float]] = None
    country_code: str = "IND"

    def __post_init__(self) -> None:
        if self.geometry is None and (self.lat is None or self.lon is None):
            if self.admin2 is None and self.admin1 is None and self.country is None:
                raise ValueError(
                    f"CityDefinition '{self.name}' needs either geometry, "
                    "lat/lon, or at least one of country/admin1/admin2."
                )

    @property
    def has_point_geometry(self) -> bool:
        return self.lat is not None and self.lon is not None

    @property
    def has_explicit_geometry(self) -> bool:
        return self.geometry is not None

    def __repr__(self) -> str:
        parts = [self.name]
        if self.admin2:
            parts.append(self.admin2)
        if self.admin1:
            parts.append(self.admin1)
        if self.country:
            parts.append(self.country)
        return f"CityDefinition({', '.join(parts)})"


@dataclass
class RadianceSeries:
    """Holds processed radiance and derived economic data for a city.

    Args:
        city: City/region name.
        df: Full monthly time-series DataFrame with columns:
            date, year, month, radiance_raw, radiance_corrected,
            cf_obs, gdp_proxy, gdp_per_capita, gdp_ppp_per_capita.
        geometry_area_km2: Area of the analysis geometry in km².
        population_by_year: Dict mapping year → population estimate.
        ppp_factors: Dict mapping year → PPP conversion factor (LCU per intl $).
        metadata: Dict with provenance info (collection, date range, base year, etc.).
    """

    city: str
    df: pd.DataFrame
    geometry_area_km2: float
    population_by_year: dict[int, float]
    ppp_factors: dict[int, float]
    metadata: dict = field(default_factory=dict)

    @property
    def base_year(self) -> int:
        return self.metadata.get("base_year", int(self.df["year"].iloc[0]))

    @property
    def start_year(self) -> int:
        return int(self.df["year"].min())

    @property
    def end_year(self) -> int:
        return int(self.df["year"].max())

    @property
    def annual_df(self) -> pd.DataFrame:
        """Annual averages from the monthly series."""
        cols = [c for c in ["radiance_corrected", "radiance_raw", "gdp_proxy",
                             "gdp_per_capita", "gdp_ppp_per_capita", "cf_obs"]
                if c in self.df.columns]
        return self.df.groupby("year")[cols].mean().reset_index()

    def __repr__(self) -> str:
        return (
            f"RadianceSeries(city='{self.city}', "
            f"years={self.start_year}–{self.end_year}, "
            f"rows={len(self.df)})"
        )
