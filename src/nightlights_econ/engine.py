"""NighttimeLightsEngine — main extraction pipeline via Google Earth Engine."""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from .core import CityDefinition, RadianceSeries
from .cloud_correction import correct_cloud_bias
from .gdp_proxy import compute_all_metrics
from .population import get_population_series
from .ppp import fetch_ppp_factors
from .utils import (
    VIIRS_COLLECTION,
    RADIANCE_BAND,
    CF_BAND,
    RADIANCE_CAP,
    HENDERSON_ELASTICITY,
    date_range_monthly,
)


class NighttimeLightsEngine:
    """Main analysis pipeline: geometry resolution → VIIRS extraction → correction → GDP proxy.

    Args:
        project_id: Google Cloud project ID for Earth Engine authentication.
        service_account: Optional service account email for non-interactive auth.
        credentials_file: Optional path to service account JSON key.
        scale: GEE pixel scale in meters for reduce operations (default 500).
        elasticity: Henderson elasticity for GDP proxy (default 0.88).
    """

    def __init__(
        self,
        project_id: Optional[str] = None,
        service_account: Optional[str] = None,
        credentials_file: Optional[str] = None,
        scale: int = 500,
        elasticity: float = HENDERSON_ELASTICITY,
    ) -> None:
        self.project_id = project_id
        self.service_account = service_account
        self.credentials_file = credentials_file
        self.scale = scale
        self.elasticity = elasticity
        self._ee = None

    def _init_ee(self) -> None:
        """Initialize Google Earth Engine (lazy)."""
        if self._ee is not None:
            return
        try:
            import ee
        except ImportError:
            raise ImportError(
                "earthengine-api is required. Run: pip install earthengine-api\n"
                "Then authenticate with: earthengine authenticate"
            )

        try:
            if self.service_account and self.credentials_file:
                credentials = ee.ServiceAccountCredentials(
                    self.service_account, self.credentials_file
                )
                if self.project_id:
                    ee.Initialize(credentials, project=self.project_id)
                else:
                    ee.Initialize(credentials)
            elif self.project_id:
                ee.Initialize(project=self.project_id)
            else:
                ee.Initialize()
        except Exception as exc:
            raise RuntimeError(
                "Google Earth Engine authentication failed.\n"
                "Run `earthengine authenticate` in your terminal, or pass "
                "project_id to NighttimeLightsEngine.\n"
                f"Original error: {exc}"
            ) from exc

        self._ee = ee

    def resolve_geometry(self, city: CityDefinition):
        """Convert a CityDefinition to an ee.Geometry.

        Args:
            city: CityDefinition instance.

        Returns:
            ee.Geometry object.
        """
        self._init_ee()
        ee = self._ee

        if city.has_explicit_geometry:
            geom = city.geometry
            if isinstance(geom, dict):
                return ee.Geometry(geom)
            return geom

        if city.has_point_geometry and city.radius_km:
            center = ee.Geometry.Point([city.lon, city.lat])
            return center.buffer(city.radius_km * 1000)

        # Use GAUL administrative boundaries
        gaul = ee.FeatureCollection("FAO/GAUL/2015/level2")

        if city.admin2:
            filtered = gaul.filter(ee.Filter.eq("ADM2_NAME", city.admin2))
            if city.admin1:
                filtered = filtered.filter(ee.Filter.eq("ADM1_NAME", city.admin1))
            if city.country:
                filtered = filtered.filter(ee.Filter.eq("ADM0_NAME", city.country))
            features = filtered.limit(1)
            feature = features.first()
            geom = feature.geometry()
            return geom

        if city.admin1:
            gaul1 = ee.FeatureCollection("FAO/GAUL/2015/level1")
            filtered = gaul1.filter(ee.Filter.eq("ADM1_NAME", city.admin1))
            if city.country:
                filtered = filtered.filter(ee.Filter.eq("ADM0_NAME", city.country))
            return filtered.geometry()

        if city.country:
            gaul0 = ee.FeatureCollection("FAO/GAUL/2015/level0")
            return gaul0.filter(ee.Filter.eq("ADM0_NAME", city.country)).geometry()

        raise ValueError(
            f"Cannot resolve geometry for '{city.name}'. "
            "Provide geometry, lat/lon+radius, or admin boundary names."
        )

    def _compute_area_km2(self, geometry) -> float:
        """Return area of a GEE geometry in km²."""
        area_m2 = geometry.area(maxError=100).getInfo()
        return float(area_m2) / 1e6

    def _extract_viirs_monthly(
        self,
        geometry,
        start_year: int,
        end_year: int,
    ) -> pd.DataFrame:
        """Extract monthly VIIRS radiance and cloud-free observation count.

        Args:
            geometry: ee.Geometry.
            start_year: First year (inclusive).
            end_year: Last year (inclusive).

        Returns:
            DataFrame with columns: date, year, month, radiance_raw, cf_obs.
        """
        self._init_ee()
        ee = self._ee

        collection = (
            ee.ImageCollection(VIIRS_COLLECTION)
            .filterDate(f"{start_year}-01-01", f"{end_year + 1}-01-01")
            .filterBounds(geometry)
        )

        records = []
        images_info = collection.getInfo()

        for feat in images_info.get("features", []):
            props = feat.get("properties", {})
            img_id = feat["id"]
            img = ee.Image(img_id)

            # Cap radiance to exclude gas flares / fires
            rad_img = img.select(RADIANCE_BAND).min(ee.Image.constant(RADIANCE_CAP))
            cf_img = img.select(CF_BAND)

            result = (
                rad_img.addBands(cf_img)
                .reduceRegion(
                    reducer=ee.Reducer.mean(),
                    geometry=geometry,
                    scale=self.scale,
                    maxPixels=1e9,
                )
                .getInfo()
            )

            rad_val = result.get(RADIANCE_BAND)
            cf_val = result.get(CF_BAND)

            if rad_val is None:
                rad_val = np.nan
            if cf_val is None:
                cf_val = np.nan

            date_str = props.get("system:index", "")[:8]
            try:
                date = pd.Timestamp(f"{date_str[:4]}-{date_str[4:6]}-01")
            except Exception:
                continue

            records.append({
                "date": date,
                "year": date.year,
                "month": date.month,
                "radiance_raw": float(rad_val),
                "cf_obs": float(cf_val),
            })

        if not records:
            raise RuntimeError(
                f"No VIIRS data returned for the specified geometry and date range "
                f"{start_year}–{end_year}."
            )

        df = pd.DataFrame(records).sort_values("date").reset_index(drop=True)
        return df

    def analyze(
        self,
        city: CityDefinition,
        start_year: int = 2014,
        end_year: int = 2026,
        base_year: Optional[int] = None,
        cf_threshold: int = 8,
    ) -> RadianceSeries:
        """Run the full analysis pipeline for a single city.

        Args:
            city: CityDefinition instance.
            start_year: First year of VIIRS data to extract.
            end_year: Last year of VIIRS data to extract.
            base_year: Reference year for index normalization (default: start_year).
            cf_threshold: Cloud-free observation threshold for correction.

        Returns:
            RadianceSeries with all derived metrics.
        """
        if base_year is None:
            base_year = start_year

        self._init_ee()
        geometry = self.resolve_geometry(city)
        area_km2 = self._compute_area_km2(geometry)

        df = self._extract_viirs_monthly(geometry, start_year, end_year)
        df = correct_cloud_bias(df, cf_threshold=cf_threshold)

        target_years = list(range(start_year, end_year + 1))
        population_by_year = get_population_series(
            city, target_years=target_years, geometry=geometry
        )
        ppp_factors = fetch_ppp_factors(city.country_code, start_year, end_year)

        df = compute_all_metrics(
            df,
            base_year=base_year,
            population_by_year=population_by_year,
            ppp_factors=ppp_factors,
            elasticity=self.elasticity,
        )

        metadata = {
            "base_year": base_year,
            "start_year": start_year,
            "end_year": end_year,
            "elasticity": self.elasticity,
            "cf_threshold": cf_threshold,
            "collection": VIIRS_COLLECTION,
            "country_code": city.country_code,
        }

        return RadianceSeries(
            city=city.name,
            df=df,
            geometry_area_km2=area_km2,
            population_by_year=population_by_year,
            ppp_factors=ppp_factors,
            metadata=metadata,
        )

    def analyze_many(
        self,
        cities: list[CityDefinition],
        start_year: int = 2014,
        end_year: int = 2026,
        base_year: Optional[int] = None,
    ) -> list[RadianceSeries]:
        """Analyze multiple cities sequentially.

        Args:
            cities: List of CityDefinition instances.
            start_year: First year.
            end_year: Last year.
            base_year: Reference year for normalization.

        Returns:
            List of RadianceSeries, one per city.
        """
        results = []
        for city in cities:
            print(f"  Analyzing {city.name}…")
            try:
                s = self.analyze(city, start_year=start_year, end_year=end_year, base_year=base_year)
                results.append(s)
            except Exception as exc:
                print(f"  WARNING: Failed for {city.name}: {exc}")
        return results
